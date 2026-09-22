"""统一检索入口契约。

收归此前散在三处的检索（CLI / channel_runner / orchestrator），
统一成带 score 的 Chunk。

score 的定位（重要）：**给排序和短路用，不给判定当输入**。
Jev 读的是检索回来的**文本**——读内容比读一个数字信息量大得多，
用数字当判定输入是假精度。分数的真实价值是：
- 排序
- 便宜的短路：全空就直接判定「不够」，省一次 Jev 调用
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openagentic.memory.manager import MemoryManager
from openagentic.retrieval import Chunk, retrieve


@pytest.fixture
def mgr(tmp_path: Path) -> MemoryManager:
    m = MemoryManager(base_dir=tmp_path / ".openagentic" / "memory")
    m.save_episode("部署经验", "用 systemd 管理服务，重启后自动恢复", ["deploy"])
    m.save_procedure("回滚流程", "如何回滚版本", "服务挂了", ["stop", "切版本", "start"])
    m.save_core_memory("lang", "用户偏好中文回答", "preference", 0.9)
    return m


async def test_retrieve_returns_chunks_with_scores(mgr):
    chunks = await retrieve("systemd", memory=mgr)
    assert chunks
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.score > 0 for c in chunks)
    assert all(c.source in {"episodic", "procedural", "core"} for c in chunks)


async def test_retrieve_respects_sources(mgr):
    only_ep = await retrieve("systemd", sources=("episodic",), memory=mgr)
    assert only_ep and all(c.source == "episodic" for c in only_ep)


async def test_retrieve_returns_empty_when_no_hit(mgr):
    """全空是「一定不够」的短路信号，必须如实返回空而不是编内容。"""
    assert await retrieve("完全不相关的词xyz", memory=mgr) == []


async def test_retrieve_skips_knowledge_without_db(mgr):
    """CLI 路径没有 DB——knowledge 必须被安静跳过，不能报错。"""
    chunks = await retrieve("systemd", memory=mgr, db=None, kb_ids=["x"])
    assert all(c.source != "knowledge" for c in chunks)


async def test_chunks_have_text_for_jev(mgr):
    """判定靠文本，不是靠分数——每块必须带可读内容。"""
    chunks = await retrieve("systemd", memory=mgr)
    assert all(c.text.strip() for c in chunks)
