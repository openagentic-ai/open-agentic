"""守护闭环契约。

背景：模型不可用时（进程没起、被别的进程抢占显存）此前没有任何东西负责把它拉起来，
全靠人手动敲 curl——2026-09-22 的 27B 反复起不来就是这个缺口。

设计要点：
- ensure 内含最长 900 秒的阻塞调用（拉起模型），必须在线程里跑，否则会卡死事件循环
- 单次失败不能让循环退出，否则一次网络抖动就永久失去守护
- 测试用 asyncio.run 而非 pytest-asyncio：modeld 跑在系统 python3 上，刻意不引入额外依赖
"""

from __future__ import annotations

import asyncio
import threading

from app.watch import run_watch_loop


def _run(ensure, interval_sec, run_for):
    stop = asyncio.Event()

    async def main():
        async def stopper():
            await asyncio.sleep(run_for)
            stop.set()

        await asyncio.gather(run_watch_loop(ensure, interval_sec=interval_sec, stop=stop), stopper())

    asyncio.run(main())


def test_loop_calls_ensure_repeatedly():
    calls = []

    def ensure():
        calls.append(1)
        return {"action": "none"}

    _run(ensure, 0.01, 0.08)
    assert len(calls) >= 3


def test_loop_survives_ensure_exception():
    """单次失败不能让守护循环退出——否则一次网络抖动就永久失去守护。"""
    calls = []

    def ensure():
        calls.append(1)
        raise RuntimeError("boom")

    _run(ensure, 0.01, 0.08)
    assert len(calls) >= 3


def test_loop_runs_ensure_off_event_loop():
    """ensure 是阻塞调用（最长 900s），必须在别的线程跑，不能卡住事件循环。"""
    main_thread = threading.current_thread().name
    seen = []

    def ensure():
        seen.append(threading.current_thread().name)
        return {"action": "none"}

    _run(ensure, 0.01, 0.05)
    assert seen, "ensure 没被调用"
    assert all(t != main_thread for t in seen), f"ensure 跑在主线程上: {seen}"


def test_loop_exits_immediately_when_stop_already_set():
    calls = []

    def ensure():
        calls.append(1)
        return {"action": "none"}

    stop = asyncio.Event()
    stop.set()
    asyncio.run(run_watch_loop(ensure, interval_sec=0.01, stop=stop))
    assert calls == []
