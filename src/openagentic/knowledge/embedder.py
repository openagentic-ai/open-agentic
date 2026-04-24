"""模块说明（中文）：`src/openagentic/knowledge/embedder.py`。\n\n该文件属于知识库模块，处理文档、向量与检索能力。\n"""

import httpx

from openagentic.config import SETTINGS


async def embed_texts(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
    """Generate embeddings for a list of texts using Ollama embed API."""
    embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for text in texts:
            resp = await client.post(
                f"{SETTINGS.OLLAMA_API_BASE}/api/embed",
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings.append(data["embeddings"][0])
    return embeddings


async def embed_single(text: str, model: str = "nomic-embed-text") -> list[float]:
    """Generate embedding for a single text."""
    result = await embed_texts([text], model)
    return result[0]
