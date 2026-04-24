"""模块说明（中文）：`src/openagentic/core/llm/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

import json
from collections.abc import AsyncGenerator

import litellm

from openagentic.core.llm.provider_config import get_provider_store

# Configure LiteLLM
litellm.drop_params = True


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict:
    """Non-streaming chat completion."""
    model, api_base, api_key = get_provider_store().resolve_runtime(model)
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        api_base=api_base,
        api_key=api_key,
    )
    choice = response.choices[0]
    usage = response.usage
    return {
        "content": choice.message.content or "",
        "model": response.model,
        "finish_reason": choice.finish_reason,
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        },
    }


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Streaming chat completion, yields SSE-formatted events."""
    model, api_base, api_key = get_provider_store().resolve_runtime(model)
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        api_base=api_base,
        api_key=api_key,
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
