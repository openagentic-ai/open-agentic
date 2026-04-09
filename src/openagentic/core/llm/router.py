"""LLM API routes (models listing, etc.)."""

from fastapi import APIRouter

from openagentic.config import settings

router = APIRouter(prefix="/api", tags=["llm"])


@router.get("/models")
async def list_models():
    """List available models. Returns the default model for now."""
    return {
        "models": [
            {
                "id": settings.litellm_default_model,
                "name": settings.litellm_default_model.split("/")[-1],
                "provider": settings.litellm_default_model.split("/")[0],
            }
        ]
    }
