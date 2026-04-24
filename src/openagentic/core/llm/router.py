"""模块说明（中文）：`src/openagentic/core/llm/router.py`。\n\n该文件定义 HTTP 路由与请求入口，负责参数校验与服务层调用。\n"""

from fastapi import APIRouter

from openagentic.core.llm import schemas
from openagentic.core.llm.provider_config import get_provider_store

router = APIRouter(prefix="/api", tags=["llm"])


@router.get("/models")
async def list_models():
    """List available models from configured provider profiles."""
    config = get_provider_store().get()
    models: list[dict] = []
    for profile in config.profiles:
        if not profile.enabled:
            continue
        for model_id in profile.models:
            models.append(
                {
                    "id": model_id,
                    "name": model_id.split("/")[-1],
                    "provider": profile.id,
                }
            )
    if not models:
        default_model = config.default_model
        models.append(
            {
                "id": default_model,
                "name": default_model.split("/")[-1],
                "provider": default_model.split("/")[0] if "/" in default_model else "unknown",
            }
        )
    return {"default_model": config.default_model, "models": models}


@router.get("/llm/providers")
async def get_provider_profiles():
    """Get persisted provider profiles (API key is masked)."""
    return get_provider_store().get().to_public_dict()


@router.put("/llm/providers/{provider_id}")
async def upsert_provider_profile(provider_id: str, body: schemas.ProviderProfileUpdate):
    config = get_provider_store().upsert_profile(
        profile_id=provider_id,
        display_name=body.display_name,
        api_base=body.api_base,
        api_key=body.api_key,
        models=body.models,
        enabled=body.enabled,
    )
    return config.to_public_dict()


@router.put("/llm/default-model")
async def update_default_model(body: schemas.DefaultModelUpdate):
    config = get_provider_store().set_default_model(body.model)
    return config.to_public_dict()
