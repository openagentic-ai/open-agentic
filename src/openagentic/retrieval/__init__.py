"""模块说明（中文）：`src/openagentic/retrieval/__init__.py`。

统一检索入口——收归此前散在三处的检索（CLI / channel_runner / orchestrator）。

设计要点：

- **score 的定位**：给**排序与短路**用，**不给判定当输入**。Jev 读的是检索回来的
  文本，读内容比读一个数字信息量大得多——用数字当判定输入是假精度。
  分数的真实价值是排序，以及「全空 ⇒ 一定不够」的便宜短路（省一次 Jev 调用）。
- **各来源分数不归一**：memory 是关键词命中数、knowledge 是 0-1 余弦，
  强行统一会造出不可比的精度。按来源各自排序即可。

knowledge（向量检索）**尚未接入**：2026-09-23 核查发现整条链路是断的——
PostgreSQL 没在跑、Xinference 没注册 embedding 模型、embedder 协议也打错了地址。
接入位留在 `retrieve()` 的 `db` / `kb_ids` 参数上，链路修通后在此合并。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from openagentic.memory.manager import MemoryManager

SOURCES: tuple[str, ...] = ("episodic", "procedural", "core")


@dataclass(frozen=True)
class Chunk:
    source: str
    text: str
    score: float
    title: str = ""
    meta: dict = field(default_factory=dict)


async def retrieve(
    query: str,
    *,
    sources: tuple[str, ...] = SOURCES,
    top_k: int = 3,
    memory: MemoryManager | None = None,
    db: Any = None,
    kb_ids: list[str] | None = None,
) -> list[Chunk]:
    """检索并返回按 score 降序的 Chunk 列表。

    `db` / `kb_ids` 是为 knowledge 预留的接入位——当前链路未修通，
    传了也不会被使用（CLI 路径本来就没有 DB）。缺任一即安静跳过，不报错。
    """
    mgr = memory if memory is not None else MemoryManager()
    chunks: list[Chunk] = []

    if "episodic" in sources:
        eps = await _safe(mgr.search_episodes, query, top_k)
        chunks += [
            Chunk(
                source="episodic",
                text=str(e.get("summary", "")),
                score=float(e.get("score", 0.0)),
                title=str(e.get("title", "")),
                meta={"file": e.get("file", "")},
            )
            for e in eps
        ]

    if "procedural" in sources:
        procs = await _safe(mgr.search_procedures, query, top_k)
        chunks += [
            Chunk(
                source="procedural",
                text=str(p.get("content", "")),
                score=float(p.get("score", 0.0)),
                title=str(p.get("name", "")),
                meta={"file": p.get("file", "")},
            )
            for p in procs
        ]

    if "core" in sources:
        entries = await _safe(mgr.search_core, query, None, top_k)
        chunks += [
            Chunk(
                source="core",
                text=str(getattr(e, "value", "")),
                score=float(getattr(e, "score", 0.0)),
                title=str(getattr(e, "key", "")),
                meta={"category": getattr(e, "category", "")},
            )
            for e in entries
        ]

    chunks.sort(key=lambda c: -c.score)
    return chunks


async def _safe(fn, *args) -> list:
    """检索失败返回空——检索不到不该让整轮对话失败。"""
    try:
        return await asyncio.to_thread(fn, *args) or []
    except Exception:
        return []
