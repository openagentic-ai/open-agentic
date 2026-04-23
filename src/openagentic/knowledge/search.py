"""Vector similarity search using pgvector."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.knowledge.models import Chunk
from openagentic.knowledge.embedder import embed_single


async def similarity_search(
    db: AsyncSession,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    embedding_model: str = "nomic-embed-text",
) -> list[dict]:
    """Search for similar chunks using cosine distance."""
    query_embedding = await embed_single(query, embedding_model)

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
        .limit(top_k)
    )

    rows = result.all()
    return [
        {
            "id": str(row.id),
            "content": row.content,
            "chunk_index": row.chunk_index,
            "document_id": str(row.document_id),
            "score": 1 - row.distance,
        }
        for row in rows
    ]
