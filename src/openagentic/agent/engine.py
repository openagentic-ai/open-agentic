"""模块说明（中文）：`src/openagentic/agent/engine.py`。

ConversationEngine——LLM 对话 + 工具调用循环的共享底座。
CLI / 飞书 / 企微 / HTTP API 全部走这一条链路，不做平台适配。

用法：
    engine = ConversationEngine(
        model="deepseek/deepseek-v4-flash",
        api_key="sk-...",
        tools=[...],
        system_prompt="你是...",
    )
    reply = await engine.chat("帮我查今天的日程")
"""

from __future__ import annotations

import json
import structlog
from typing import Callable, Awaitable

from openagentic.agent.llm import litellm_chat

logger = structlog.get_logger("openagentic.agent.engine")

# 工具执行器签名：async (tool_name: str, arguments: dict) -> str
ToolExecutor = Callable[[str, dict], Awaitable[str]]
# 预检查回调签名：async (tool_name: str, arguments: dict) -> bool | str
# 返回 True 表示放行；返回 str 表示拒绝（str 为拒绝原因）
ToolGuard = Callable[[str, dict], Awaitable[bool | str]]

DEFAULT_MAX_ITERATIONS = 5


class ConversationEngine:
    """LLM 对话引擎：发送消息 → 调工具 → 追加结果 → 循环 → 最终回复。

    无状态设计——调用方自行管理 messages 历史和持久化。
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        tools: list[dict],
        system_prompt: str,
        api_base: str | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        executor: ToolExecutor | None = None,
        guard: ToolGuard | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.executor = executor
        self.guard = guard

    # -- 单轮对话（自行管理 messages）--------------------------------------

    async def chat(self, messages: list[dict]) -> str:
        """运行工具调用循环，返回最终文本回复。

        messages: [{"role": "system"|"user"|"assistant"|"tool", ...}]
        返回 assistant 的文本回复（不含 tool_calls）。
        """
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            result = await litellm_chat(
                messages=messages,
                model=self.model,
                api_base=self.api_base,
                api_key=self.api_key,
                tools=self.tools,
            )
            msg = result["message"]
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls", [])
            thinking = msg.get("thinking", "")

            # 纯文本 → 结束
            if content and not tool_calls:
                return content

            # 工具调用 → 执行并追加
            if tool_calls:
                entry: dict = {"role": "assistant", "content": content, "tool_calls": tool_calls}
                if thinking:
                    entry["reasoning_content"] = thinking
                messages.append(entry)

                for tc in tool_calls:
                    tool_result = await self._execute_tool(tc, messages)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
                continue

            # thinking 模式返回空 content 但有 reasoning → 用 reasoning 作为回复
            if thinking and not tool_calls:
                logger.debug("DeepSeek thinking-only response, using reasoning_content as reply")
                return thinking

            # 兜底
            if content:
                return content
            return ""

        logger.warning("ConversationEngine max iterations reached", max_iterations=self.max_iterations)
        # 达到工具调用上限，注入收束指令让 LLM 基于已收集的信息给结论
        messages.append({
            "role": "user",
            "content": (
                "已达到工具调用次数上限。请基于已获取的所有信息，"
                "直接给出你的结论或下一步建议，不要再调用工具。"
            ),
        })
        try:
            result = await litellm_chat(
                messages=messages,
                model=self.model,
                api_base=self.api_base,
                api_key=self.api_key,
                tools=[],  # 禁止再调工具
            )
            final_content = result["message"].get("content") or result["message"].get("reasoning_content") or ""
            if final_content:
                return final_content
        except Exception:
            logger.exception("force-conclusion chat failed")

        # 兜底：取最后一轮 assistant 内容
        last_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_content = msg.get("content") or msg.get("reasoning_content") or ""
                if last_content:
                    break
        return last_content

    async def _execute_tool(self, tc: dict, messages: list[dict]) -> str:
        """执行单个工具调用，返回结果字符串。"""
        func_name = tc["function"]["name"]
        try:
            func_args = json.loads(tc["function"]["arguments"])
        except (json.JSONDecodeError, KeyError):
            func_args = {}

        # 安全门
        if self.guard:
            allowed = await self.guard(func_name, func_args)
            if allowed is not True:
                reason = allowed if isinstance(allowed, str) else "工具调用被拒绝"
                logger.warning("Tool guard blocked", tool=func_name, reason=reason)
                return reason

        # 执行
        if self.executor:
            logger.info("Tool dispatch", tool=func_name,
                        args_preview=str(func_args)[:200])
            try:
                result = await self.executor(func_name, func_args)
                return result
            except Exception as e:
                logger.exception("Tool executor failed", tool=func_name)
                return f"工具执行错误：{e}"

        return f"工具 {func_name} 未配置执行器"
