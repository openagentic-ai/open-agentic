"""模块说明（中文）：`src/openagentic/retrieval/knowledge.py`。

知识库召回 + Jev 精排——**不用 embedding 的 RAG**。

分工：

| 环节 | 谁做 | 怎么做 |
|---|---|---|
| **召回** | 代码 | n-gram ILIKE。中文没空格，整句 ILIKE 匹配不上，n-gram 片段才能落到文档里 |
| **精排** | Jev | 逐条判相关性，返回**校准概率**。这是 embedding 原本干的「语义匹配」 |

为什么精排交给 Jev 而不是 embedding：
- 相关性判断本来就是一个 `decide` primitive，RLCD 是它该待的地方
- 返回的是校准概率，不是余弦距离——**判得更准且可解释**
- 省掉整套向量设施：不需要 embedding 模型、不需要维度对齐、不需要 GPU

**明确的边界（必须知道）**：
- 代码召回是**字面匹配**，语义相近但用词不同的会**漏召**。
  **Jev 只能从召回到的候选里挑，挑不出没被召回的。**
- 因此本方案适用于**个人知识库**（几十到几百条 chunk）；
  企业级语料需要真正的向量召回，那时再引入 embedding。
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from typing import Any

import structlog

from openagentic.control_plane.jev import build_jev
from openagentic.retrieval import Chunk

logger = structlog.get_logger("openagentic.retrieval.knowledge")

# 判为相关的 noul 阈值
RELEVANCE_THRESHOLD = 0.5
# 每批送 Jev 的候选数。RLCD 窗口小，候选文本又长，一批塞不了太多。
DEFAULT_BATCH_SIZE = 4
DEFAULT_RECALL_LIMIT = 30

_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)


def ngram_terms(query: str, n: int = 2) -> list[str]:
    """从 query 提取连续 n 字片段作为召回词（去重、保序）。

    中文没有空格，整句 ILIKE 匹配不上；n=2 是中文的最小有意义单位。
    """
    cleaned = _PUNCT.sub("", query)
    if not cleaned:
        return []
    if len(cleaned) <= n:
        return [cleaned]

    seen: dict[str, None] = {}
    for i in range(len(cleaned) - n + 1):
        seen.setdefault(cleaned[i:i + n], None)
    return list(seen)


async def recall(
    db: Any, kb_ids: list[Any], query: str, *, limit: int = DEFAULT_RECALL_LIMIT,
) -> list[Chunk]:
    """代码召回：n-gram ILIKE OR 匹配。不做语义匹配——那是精排的活。"""
    terms = ngram_terms(query)
    if not terms or not kb_ids:
        return []

    try:
        from sqlalchemy import or_, select

        from openagentic.knowledge.models import Chunk as ChunkRow

        conds = [ChunkRow.content.ilike(f"%{t}%") for t in terms]
        stmt = (
            select(ChunkRow)
            .where(ChunkRow.knowledge_base_id.in_(kb_ids), or_(*conds))
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
    except Exception:
        logger.warning("knowledge recall failed", exc_info=True)
        return []

    return [
        Chunk(
            source="knowledge",
            text=str(r.content),
            score=0.0,  # 召回阶段没有相关性信号，等精排给
            title=str(getattr(r, "document_id", "")),
            meta={"chunk_id": str(getattr(r, "id", "")), "index": getattr(r, "chunk_index", 0)},
        )
        for r in rows
    ]


async def _judge_batch(query: str, batch: list[Chunk], jev: Any) -> list[float | None] | None:
    """一批候选一次 fan-out 问完。失败返回 None（调用方 fail-open）。"""
    state = {
        "query": query,
        "candidates": [{"id": f"c{i}", "text": c.text} for i, c in enumerate(batch)],
    }
    questions = {
        f"c{i}": {
            "type": "noul",
            "instructions": f"候选 c{i} 的内容与 query 相关吗？",
        }
        for i in range(len(batch))
    }

    try:
        answers = await asyncio.to_thread(jev.ask, state, questions)
    except Exception:
        logger.warning("knowledge rerank failed, failing open", exc_info=True)
        return None

    if not isinstance(answers, dict):
        return None

    out: list[float | None] = []
    for i in range(len(batch)):
        val = (answers.get(f"c{i}") or {}).get("noul")
        out.append(float(val) if isinstance(val, (int, float)) else None)
    return out


async def rerank(
    query: str,
    candidates: list[Chunk],
    *,
    jev: Any = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[Chunk]:
    """Jev 精排：分批判相关性，只留判为相关的。

    失败一律 fail-open——精排挂掉不能把召回结果也弄丢。
    """
    if not candidates:
        return []

    client = jev if jev is not None else build_jev()
    if client is None:
        return candidates

    kept: list[Chunk] = []
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start:start + batch_size]
        scores = await _judge_batch(query, batch, client)
        if scores is None:
            kept.extend(batch)
            continue
        for chunk, score in zip(batch, scores):
            if score is not None and score >= RELEVANCE_THRESHOLD:
                kept.append(replace(chunk, score=score))
    return kept


async def retrieve_knowledge(
    db: Any,
    kb_ids: list[Any],
    query: str,
    *,
    jev: Any = None,
    recall_limit: int = DEFAULT_RECALL_LIMIT,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[Chunk]:
    """召回 → 精排。任一环节不可用都安静降级。"""
    candidates = await recall(db, kb_ids, query, limit=recall_limit)
    if not candidates:
        return []
    return await rerank(query, candidates, jev=jev, batch_size=batch_size)
