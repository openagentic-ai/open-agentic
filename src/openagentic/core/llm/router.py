"""模块说明（中文）：`src/openagentic/core/llm/router.py`。

LLM 网关 HTTP API 路由：模型列表、Provider 配置管理、默认模型切换。
"""

from fastapi import APIRouter

from openagentic.core.llm import schemas
from openagentic.core.llm.provider_config import get_provider_store

router = APIRouter(prefix="/api", tags=["llm"])


@router.get("/models")
async def list_models():
    """列出所有已启用 provider 的模型。

    返回格式：{"default_model": "...", "models": [{"id": ..., "name": ..., "provider": ...}]}
    若无已启用 provider 的模型，至少回退到默认模型。
    """
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

    # 回退：确保至少返回一个模型
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
    """获取持久化的 provider 配置（API Key 已脱敏）。"""
    return get_provider_store().get().to_public_dict()


@router.put("/llm/providers/{provider_id}")
async def upsert_provider_profile(provider_id: str, body: schemas.ProviderProfileUpdate):
    """创建或更新 provider 配置（API Key / API Base / 模型列表等）。"""
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
    """切换默认模型。"""
    config = get_provider_store().set_default_model(body.model)
    return config.to_public_dict()
