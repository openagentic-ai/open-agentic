"""ConcurrencyGate 单测——覆盖核心契约：

1. submit 正常返回值
2. 同 session_key 严格串行（不交错）
3. 全局信号量上限生效
4. 类别信号量上限生效
5. 排队上限触发 GateBusy
6. 整体超时触发 GateTimeout
7. 异常向上传播
8. session_key 为空时不串行（独立请求并行）
9. 令牌桶限流生效
10. acquire 上下文管理器（细粒度局部限流）
"""

from __future__ import annotations

import asyncio
import time

import pytest

from openagentic.concurrency import ConcurrencyGate, GateBusy, GateTimeout
from openagentic.concurrency.config import CategoryConfig, GateConfig


pytestmark = pytest.mark.asyncio


def _gate(**overrides) -> ConcurrencyGate:
    """构造测试用 gate，可按需覆盖默认配置。"""
    base = GateConfig()
    fields = dict(
        global_concurrency=overrides.pop("global_concurrency", base.global_concurrency),
        max_queued=overrides.pop("max_queued", base.max_queued),
        default_timeout=overrides.pop("default_timeout", base.default_timeout),
        categories=overrides.pop("categories", base.categories),
    )
    return ConcurrencyGate(GateConfig(**fields))


async def test_submit_returns_result():
    g = _gate()

    async def work():
        return 42

    result = await g.submit("k1", work)
    assert result == 42


async def test_same_session_key_serializes():
    """同 session_key 必须串行，不能交错。"""
    g = _gate()
    order: list[str] = []

    async def work(name: str):
        order.append(f"{name}-start")
        await asyncio.sleep(0.05)
        order.append(f"{name}-end")
        return name

    # 两个协程同 key 并发提交——应该一个完整跑完才轮到另一个
    results = await asyncio.gather(
        g.submit("session-A", lambda: work("A")),
        g.submit("session-A", lambda: work("B")),
    )
    assert sorted(results) == ["A", "B"]
    # start 和 end 必须连续，不能交错（A-start, B-start, A-end, B-end 是错的）
    assert order in [
        ["A-start", "A-end", "B-start", "B-end"],
        ["B-start", "B-end", "A-start", "A-end"],
    ]


async def test_different_session_keys_run_in_parallel():
    """不同 session_key 必须并行，不互相阻塞。"""
    g = _gate()
    started = asyncio.Event()
    proceed = asyncio.Event()

    async def work(name: str):
        started.set()
        await proceed.wait()
        return name

    # A 在跑，B 应该能立刻进入
    task_a = asyncio.create_task(g.submit("A", lambda: work("a")))
    await started.wait()  # 确认 A 已启动

    started.clear()
    task_b = asyncio.create_task(g.submit("B", lambda: work("b")))
    await asyncio.wait_for(started.wait(), timeout=0.5)  # B 也启动了

    proceed.set()
    await asyncio.gather(task_a, task_b)


async def test_empty_session_key_does_not_serialize():
    """session_key 为空时不串行——HTTP 单次调用语义。"""
    g = _gate()
    in_flight = 0
    max_seen = 0

    async def work():
        nonlocal in_flight, max_seen
        in_flight += 1
        max_seen = max(max_seen, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1

    await asyncio.gather(*[g.submit("", work) for _ in range(5)])
    assert max_seen >= 2  # 至少有两个同时在跑


async def test_global_concurrency_limit():
    """全局信号量上限：超过上限的会等待，最多并发数 == 上限。"""
    g = _gate(global_concurrency=2)
    in_flight = 0
    max_seen = 0

    async def work():
        nonlocal in_flight, max_seen
        in_flight += 1
        max_seen = max(max_seen, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1

    # 5 个任务，全局上限 2，应该最多看到 2 个并发
    await asyncio.gather(*[g.submit("", work) for _ in range(5)])
    assert max_seen == 2


async def test_category_concurrency_limit():
    """类别信号量上限——独立于全局上限。"""
    cats = {
        "default": CategoryConfig(concurrency=10),
        "llm": CategoryConfig(concurrency=2),
    }
    g = _gate(global_concurrency=10, categories=cats)
    in_flight = 0
    max_seen = 0

    async def work():
        nonlocal in_flight, max_seen
        in_flight += 1
        max_seen = max(max_seen, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1

    await asyncio.gather(*[
        g.submit("", work, category="llm") for _ in range(5)
    ])
    assert max_seen == 2


async def test_max_queued_raises_busy():
    """排队上限：超过 max_queued 直接抛 GateBusy。"""
    g = _gate(global_concurrency=1, max_queued=2)
    blocker_proceed = asyncio.Event()

    async def blocker():
        await blocker_proceed.wait()

    # 占住唯一槽位 + 排队 2 个 → 第 4 个直接拒
    holder = asyncio.create_task(g.submit("", blocker))
    await asyncio.sleep(0.01)  # 让 holder 进入执行
    pending1 = asyncio.create_task(g.submit("", blocker))
    pending2 = asyncio.create_task(g.submit("", blocker))
    await asyncio.sleep(0.01)  # 让两个 pending 进入排队

    with pytest.raises(GateBusy):
        await g.submit("", blocker)

    # 收尾
    blocker_proceed.set()
    holder.cancel()
    pending1.cancel()
    pending2.cancel()
    for t in (holder, pending1, pending2):
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass


async def test_timeout_raises_gate_timeout():
    """整体超时：超过 timeout 抛 GateTimeout。"""
    g = _gate()

    async def slow():
        await asyncio.sleep(1.0)
        return "done"

    with pytest.raises(GateTimeout) as exc_info:
        await g.submit("", slow, timeout=0.05)
    assert exc_info.value.stage == "overall"


async def test_exception_propagates():
    """业务异常必须向上抛，底座不吞。"""
    g = _gate()

    async def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await g.submit("", fail)


async def test_token_bucket_limits_rate():
    """令牌桶限流：5 req/s + burst 2，10 个请求至少要 1.5s 多。"""
    cats = {
        "default": CategoryConfig(concurrency=10),
        "llm": CategoryConfig(concurrency=10, rate_per_sec=5.0, burst=2),
    }
    g = _gate(global_concurrency=10, categories=cats)

    async def work():
        return None

    start = time.monotonic()
    await asyncio.gather(*[
        g.submit("", work, category="llm") for _ in range(10)
    ])
    elapsed = time.monotonic() - start
    # burst=2 立即过，剩余 8 个按 5/s = 8/5 = 1.6s
    # 给个宽松下限避免抖动误杀
    assert elapsed >= 1.2, f"expected >=1.2s, got {elapsed:.2f}s"


async def test_acquire_context_manager():
    """细粒度 acquire——只占类别槽位，不走全局/会话锁。"""
    cats = {
        "default": CategoryConfig(concurrency=10),
        "subprocess": CategoryConfig(concurrency=2),
    }
    g = _gate(categories=cats)
    in_flight = 0
    max_seen = 0

    async def work():
        nonlocal in_flight, max_seen
        async with g.acquire("subprocess"):
            in_flight += 1
            max_seen = max(max_seen, in_flight)
            await asyncio.sleep(0.05)
            in_flight -= 1

    await asyncio.gather(*[work() for _ in range(5)])
    assert max_seen == 2


async def test_unknown_category_falls_back_to_default():
    """未知类别走 default，不抛异常。"""
    g = _gate()

    async def work():
        return "ok"

    result = await g.submit("", work, category="nonexistent")
    assert result == "ok"


async def test_stats_shape():
    """stats() 返回结构合理，字段齐全。"""
    g = _gate()

    async def work():
        return None

    await g.submit("k", work)
    s = g.stats()
    assert s["counters"]["submitted"] == 1
    assert s["counters"]["completed"] == 1
    assert "global_concurrency" in s["config"]
    assert isinstance(s["categories"], list)
    assert "active_keys" in s["session_locks"]
