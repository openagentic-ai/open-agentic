"""模块说明（中文）：`src/openagentic/agent/llm.py`。

LLM 调用抽象——从 cli/llm.py 提取，供 CLI / 渠道 / HTTP API 共享。
处理 DeepSeek thinking mode 的 reasoning_content 兼容性。
"""

from __future__ import annotations

import json
import structlog
from typing import Any

import litellm

logger = structlog.get_logger("openagentic.agent.llm")


def is_deepseek_reasoning_model(model: str) -> bool:
    """Check if model is a DeepSeek reasoning/thinking model."""
    lower = model.lower()
    return "deepseek" in lower and ("v4" in lower or "reasoner" in lower)


def ensure_reasoning_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure all assistant messages have reasoning_content for DeepSeek thinking mode.

    DeepSeek API requires reasoning_content on every assistant message when
    thinking mode is enabled, even if the original response had no thinking.
    """
    patched = []
    for msg in messages:
        if msg.get("role") == "assistant" and "reasoning_content" not in msg:
            msg = {**msg, "reasoning_content": ""}
        patched.append(msg)
    return patched



async def _escalate_if_configured(kwargs: dict, cp_cfg) -> Any | None:
    """本地后端失败时转云端。

    未配置升级目标、或升级自身也失败，一律返回 None——由调用方抛出原始错误，
    避免用云端故障掩盖本地故障的真因。配置解析失败同样静默回落。
    """
    from openagentic.control_plane import escalation_target

    target = escalation_target(cp_cfg)
    if not target:
        return None

    try:
        from openagentic.concurrency import get_default_gate
        from openagentic.control_plane import gate_category
        from openagentic.core.llm.provider_config import get_provider_store

        esc_model, esc_base, esc_key = get_provider_store().resolve_runtime(target)
        esc_kwargs = {**kwargs, "model": esc_model}
        if esc_base:
            esc_kwargs["api_base"] = esc_base
        if esc_key:
            esc_kwargs["api_key"] = esc_key

        async with get_default_gate().acquire(gate_category(esc_base, cp_cfg)):
            return await litellm.acompletion(**esc_kwargs)
    except Exception:
        logger.warning("escalation failed", target=target, exc_info=True)
        return None


async def litellm_chat(
    messages: list[dict[str, Any]],
    model: str,
    api_base: str | None,
    api_key: str | None,
    tools: list[dict] | None = None,
    allow_escalation: bool = True,
) -> dict:
    """Call model via LiteLLM with optional tool calling.

    返回统一格式：{"message": {"role":..., "content":..., "tool_calls":..., "thinking":...}}
    """
    is_reasoning = is_deepseek_reasoning_model(model)
    send_messages = ensure_reasoning_content(messages) if is_reasoning else messages

    # ollama profile 指向 OpenAI 兼容端点（Xinference）时，LiteLLM 需 openai 协议前缀才走 /v1/chat/completions
    if api_base and model.startswith("ollama/"):
        model = "openai/" + model.split("/", 1)[1]

    kwargs: dict = {
        "model": model,
        "messages": send_messages,
        "temperature": 0.3,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    # thinking 参数仅 DeepSeek 原生 provider 支持；OpenAI 适配器（api_base 指向 DeepSeek）不支持
    if is_reasoning and not api_base:
        kwargs["thinking"] = {"type": "enabled"}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    kwargs.setdefault("timeout", 120)

    # 走 LLM 类别配额（信号量 + 令牌桶）——保护 provider QPS、削峰填谷。
    # 每次 LLM 调用都过这一关：CLI 单次调用没影响，飞书/HTTP 高并发时自动限流。
    from openagentic.concurrency import get_default_gate
    from openagentic.control_plane import gate_category, load_control_plane_config

    cp_cfg = load_control_plane_config()
    # 按后端选配额类别：本地推理后端序列槽位有限，不能按云端 QPS 配（控制面未启用则返回 "llm"）
    category = gate_category(api_base, cp_cfg)
    try:
        async with get_default_gate().acquire(category):
            response = await litellm.acompletion(**kwargs)
    except Exception:
        if not allow_escalation:
            raise
        response = await _escalate_if_configured(kwargs, cp_cfg)
        if response is None:
            logger.exception("litellm_chat failed")
            raise

    # Best-effort cost tracking
    try:
        from openagentic.cli import cost_tracker
        cost_tracker.record(model, response)
    except Exception:  # nosec B110 — 记账是 best-effort，失败不得阻断 LLM 调用
        pass

    choice = response.choices[0]
    msg = choice.message
    tool_calls = []
    for tc in (getattr(msg, "tool_calls", None) or []):
        raw_args = tc.function.arguments if getattr(tc, "function", None) else "{}"
        if isinstance(raw_args, dict):
            args = json.dumps(raw_args, ensure_ascii=False)
        else:
            args = raw_args if isinstance(raw_args, str) else "{}"
        tool_calls.append({
            "id": getattr(tc, "id", None),
            "type": "function",
            "function": {"name": tc.function.name if getattr(tc, "function", None) else "", "arguments": args},
        })
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
