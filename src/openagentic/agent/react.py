"""Minimal ReAct-style executor for Phase 2."""

from __future__ import annotations

import re

from openagentic.agent.models import Agent
from openagentic.agent.schemas import AgentStep
from openagentic.agent.tools import ToolRegistry
from openagentic.core.llm.service import chat_completion

MATH_PATTERN = re.compile(r"[-+*/().\d\s]{3,}")


class ReactExecutor:
    """Runs a small reasoning loop with optional tool usage."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def run(self, agent: Agent, user_input: str) -> tuple[str, list[AgentStep]]:
        steps: list[AgentStep] = [AgentStep(step="think", thought="分析用户输入并决定是否调用工具")]
        allowed_tools = set(agent.tool_names or [])

        tool_name, tool_arg = self._pick_tool(user_input, allowed_tools)
        observation = None
        if tool_name:
            try:
                observation = self.registry.call(tool_name, tool_arg)
                steps.append(
                    AgentStep(
                        step="act",
                        action=f"{tool_name}({tool_arg})",
                        observation=observation,
                    )
                )
            except ValueError as exc:
                steps.append(AgentStep(step="act", action=tool_name, observation=str(exc)))

        answer = await self._final_answer(agent, user_input, observation)
        steps.append(AgentStep(step="final", thought="基于工具结果和上下文给出最终答复"))
        return answer, steps

    def _pick_tool(self, text: str, allowed_tools: set[str]) -> tuple[str | None, str]:
        clean = text.strip()
        if clean.lower().startswith("echo ") and "echo" in allowed_tools:
            return "echo", clean[5:].strip()

        if ("时间" in clean or "time" in clean.lower()) and "current_time" in allowed_tools:
            return "current_time", ""

        if "calculator" in allowed_tools and MATH_PATTERN.fullmatch(clean):
            return "calculator", clean

        return None, ""

    async def _final_answer(self, agent: Agent, user_input: str, observation: str | None) -> str:
        system = agent.system_prompt or "你是一个执行任务的智能体，请给出简洁准确的回答。"
        messages = [{"role": "system", "content": system}]
        if observation is not None:
            messages.append(
                {
                    "role": "system",
                    "content": f"工具调用结果：{observation}。请结合结果回答用户，不要编造。",
                }
            )
        messages.append({"role": "user", "content": user_input})

        try:
            result = await chat_completion(messages=messages, model=agent.model)
            return result["content"]
        except Exception:
            if observation is not None:
                return f"工具执行完成，结果：{observation}"
            return "执行完成，但当前模型不可用，请检查 LLM 配置后重试。"

