"""Generate embeddings via Ollama."""

import httpx

from openagentic.config import settings


async def embed_texts(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
    """Generate embeddings for a list of texts using Ollama embed API."""
    embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for text in texts:
            resp = await client.post(
                f"{settings.ollama_api_base}/api/embed",
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
