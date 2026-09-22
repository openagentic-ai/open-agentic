"""前置阶段编排契约。

流程：System-1 判断要不要检索 → 检索 → System-1 判够不够
      → 不够则补充上下文（更宽的检索）→ 拼成文本注入 system。

关键约束：
- 三处旧检索都是「无条件检索」，所以 route 关闭时必须**仍然检索**（向后兼容）
- 全空就短路，不浪费一次 Jev 调用
- 判定失败 / Jev 不可用 → 按「够」处理并照常注入（fail-open）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openagentic.memory.manager import MemoryManager
from openagentic.retrieval import prepare as prep
from openagentic.retrieval.prepare import compose_hooks, prepare_context


@pytest.fixture
def mgr(tmp_path: Path) -> MemoryManager:
    m = MemoryManager(base_dir=tmp_path / ".openagentic" / "memory")
    m.save_episode("部署经验", "用 systemd 管理服务，重启后自动恢复进程", ["deploy"])
    return m


class _FakeJev:
    def __init__(self, answers=None):
        self._answers = answers
        self.calls = 0

    def ask(self, state, questions, max_retries=None):
        self.calls += 1
        return self._answers


# --- 基本注入 ---------------------------------------------------------

async def test_returns_none_when_nothing_found(mgr):
    assert await prepare_context("毫无关联的词xyz", memory=mgr) is None


async def test_injects_retrieved_text(mgr):
    text = await prepare_context("systemd", memory=mgr)
    assert text and "systemd" in text


# --- 路由 -------------------------------------------------------------

async def test_route_off_still_retrieves(mgr):
    """三处旧行为都是无条件检索——route 关闭时必须保持，否则是行为倒退。"""
    text = await prepare_context("systemd", memory=mgr, route_enabled=False)
    assert text and "systemd" in text


async def test_route_says_no_retrieval_skips(mgr):
    jev = _FakeJev({"need_retrieval": {"type": "noul", "noul": 0.1}})
    text = await prepare_context("systemd", memory=mgr, route_enabled=True, jev=jev)
    assert text is None
    assert jev.calls == 1


# --- 够不够 -----------------------------------------------------------

async def test_sufficient_returns_normal_context(mgr):
    jev = _FakeJev({"enough": {"type": "noul", "noul": 0.9}})
    text = await prepare_context("systemd", memory=mgr, sufficiency_enabled=True, jev=jev)
    assert text and "资料不足" not in text


async def test_insufficient_marks_shortage(mgr):
    """判不够且补不上 → 必须带明确标记进 System-2，让它别编。"""
    jev = _FakeJev({"enough": {"type": "noul", "noul": 0.1}})
    text = await prepare_context("systemd", memory=mgr, sufficiency_enabled=True, jev=jev)
    assert text and "资料不足" in text


async def test_insufficient_triggers_wider_retrieval(mgr):
    """补充上下文：判不够时用更宽的检索再试一轮。"""
    jev = _FakeJev({"enough": {"type": "noul", "noul": 0.1}})
    calls: list[tuple] = []

    orig = prep.retrieve

    async def spy(query, **kw):
        calls.append((query, kw.get("top_k")))
        return await orig(query, **kw)

    prep.retrieve = spy
    try:
        await prepare_context("systemd", memory=mgr, sufficiency_enabled=True,
                              jev=jev, top_k=3, max_rounds=1)
    finally:
        prep.retrieve = orig
    assert len(calls) >= 2, "应该再检索一轮"
    assert calls[1][1] > calls[0][1], "第二轮应放宽 top_k"
    assert jev.calls >= 2, "补完要再判一次"


# --- 钩子合成 ---------------------------------------------------------

async def test_compose_joins_outputs():
    async def a(msgs):
        return "A"

    async def b(msgs):
        return "B"

    h = compose_hooks(a, b)
    assert h is not None
    assert await h([]) == "A\n\nB"


async def test_compose_skips_none_results():
    async def a(msgs):
        return None

    async def b(msgs):
        return "B"

    assert await compose_hooks(a, b)([]) == "B"


async def test_compose_survives_one_failing():
    """一个钩子挂了不能连累另一个——失败隔离。"""

    async def bad(msgs):
        raise RuntimeError("boom")

    async def good(msgs):
        return "OK"

    assert await compose_hooks(bad, good)([]) == "OK"


async def test_compose_returns_none_when_all_empty():
    async def a(msgs):
        return None

    # 单个钩子时 compose_hooks 直接返回原函数（不做无谓包装）
    assert await compose_hooks(a, None)([]) is None
    assert compose_hooks(None) is None
