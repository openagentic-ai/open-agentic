"""模块说明（中文）：`src/openagentic/knowledge/search.py`。\n\n该文件属于知识库模块，处理文档、向量与检索能力。\n"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.knowledge.models import Chunk
from openagentic.knowledge.embedder import embed_single


async def similarity_search(
    db: AsyncSession,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    embedding_model: str = "nomic-embed-text",
    rerank: bool = True,
    rerank_top_n: int = 20,
) -> list[dict]:
    """Search for similar chunks using cosine distance."""
    query_embedding = await embed_single(query, embedding_model)
    candidate_limit = max(top_k, rerank_top_n if rerank else top_k, top_k * 4)

    result = await db.execute(
        select(
            Chunk.id,
            Chunk.content,
            Chunk.chunk_index,
            Chunk.document_id,
            Chunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .where(Chunk.knowledge_base_id == knowledge_base_id)
        .where(Chunk.embedding.isnot(None))
        .order_by("distance")
        .limit(candidate_limit)
    )

    rows = result.all()
    results = [
        {
            "id": str(row.id),
            "content": row.content,
            "chunk_index": row.chunk_index,
            "document_id": str(row.document_id),
            "score": max(0.0, 1 - float(row.distance)),
        }
        for row in rows
    ]
    if rerank:
        results = _rerank_results(query, results)[:top_k]
    else:
        results = results[:top_k]
    return results


def _rerank_results(query: str, results: list[dict]) -> list[dict]:
    query_terms = [t.lower() for t in query.split() if t.strip()]
    if not query_terms:
        return results

    reranked = []
    for item in results:
        text = str(item.get("content", "")).lower()
        overlap = sum(1 for term in query_terms if term in text)
        lexical = overlap / max(len(query_terms), 1)
        vector_score = float(item.get("score", 0.0))
        rerank_score = 0.6 * vector_score + 0.4 * lexical
        reranked.append({**item, "rerank_score": rerank_score})

    reranked.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return reranked


async def ensure_vector_indexes(db: AsyncSession) -> list[str]:
    """Create ANN indexes for chunk retrieval."""
    statements = [
        (
            "idx_chunks_kb_embedding_ivfflat",
            "CREATE INDEX IF NOT EXISTS idx_chunks_kb_embedding_ivfflat "
            "ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",
        ),
        (
            "idx_chunks_kb_id_chunk_idx",
            "CREATE INDEX IF NOT EXISTS idx_chunks_kb_id_chunk_idx "
            "ON chunks (knowledge_base_id, chunk_index)",
        ),
    ]
    created: list[str] = []
    for index_name, sql in statements:
        try:
            await db.execute(text(sql))
            created.append(index_name)
        except Exception:
            # Some environments (SQLite/test DB) do not support pgvector indexes.
            continue
    return created
