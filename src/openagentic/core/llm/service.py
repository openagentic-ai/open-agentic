"""模块说明（中文）：`src/openagentic/core/llm/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

import json
from collections.abc import AsyncGenerator

import litellm

from openagentic.core.llm.provider_config import get_provider_store
from openagentic.tenant import get_current_request_id, get_current_tenant_id

# Configure LiteLLM
litellm.drop_params = True


def _litellm_kwargs(model: str | None = None) -> dict:
    """Build common litellm kwargs with provider resolution + request tracing."""
    model, api_base, api_key = get_provider_store().resolve_runtime(model)
    kwargs: dict = {"model": model, "api_base": api_base, "api_key": api_key}
    # 跨服务 correlation：注入 request_id/tenant_id 到 LiteLLM 调用
    extra_headers = {}
    request_id = get_current_request_id()
    if request_id:
        extra_headers["x-request-id"] = request_id
    tenant_id = get_current_tenant_id()
    if tenant_id:
        extra_headers["x-tenant-id"] = str(tenant_id)
    if extra_headers:
        kwargs["extra_headers"] = extra_headers
    return kwargs


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict:
    """Non-streaming chat completion."""
    kwargs = _litellm_kwargs(model)
    response = await litellm.acompletion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    choice = response.choices[0]
    usage = response.usage
    reasoning = getattr(choice.message, "reasoning_content", None) or getattr(choice.message, "thinking", None)
    result = {
        "content": choice.message.content or "",
        "model": response.model,
        "finish_reason": choice.finish_reason,
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        },
    }
    if reasoning:
        result["reasoning_content"] = reasoning
    return result


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Streaming chat completion, yields SSE-formatted events."""
    kwargs = _litellm_kwargs(model)
    response = await litellm.acompletion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        **kwargs,
    )

    full_content = ""
    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            full_content += delta.content
            yield f"data: {json.dumps({'event': 'token', 'data': delta.content})}\n\n"

        if chunk.choices[0].finish_reason:
            usage = getattr(chunk, "usage", None)
            yield f"data: {json.dumps({'event': 'done', 'data': full_content, 'usage': {'prompt_tokens': getattr(usage, 'prompt_tokens', 0) if usage else 0, 'completion_tokens': getattr(usage, 'completion_tokens', 0) if usage else 0}})}\n\n"
