"""模块说明（中文）：`src/openagentic/cli/llm.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import json
from typing import Any

import litellm


async def litellm_chat(
    messages: list[dict[str, Any]],
    model: str,
    api_base: str | None,
    api_key: str | None,
    tools: list[dict] | None = None,
) -> dict:
    """Call model via LiteLLM with optional tool calling."""
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "api_base": api_base or None,
        "api_key": api_key or None,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    msg = choice.message
    tool_calls = []
    for tc in (getattr(msg, "tool_calls", None) or []):
        raw_args = tc.function.arguments if getattr(tc, "function", None) else "{}"
        if isinstance(raw_args, dict):
            args = json.dumps(raw_args, ensure_ascii=False)
        else:
            args = raw_args if isinstance(raw_args, str) else "{}"
        tool_calls.append(
            {
                "id": getattr(tc, "id", None),
                "type": "function",
                "function": {
                    "name": tc.function.name if getattr(tc, "function", None) else "",
                    "arguments": args,
                },
            }
        )
    out_content = getattr(msg, "content", None)
    if tool_calls and (out_content is None or out_content == ""):
        out_content = None
    else:
        out_content = out_content or ""
    raw_thinking = getattr(msg, "thinking", None) or getattr(msg, "reasoning_content", None)
    thinking_str = "" if raw_thinking is None else str(raw_thinking)
    return {
        "message": {
            "role": getattr(msg, "role", "assistant"),
            "content": out_content,
            "tool_calls": tool_calls,
            "thinking": thinking_str,
        }
    }
