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
        steps: list[AgentStep] = [AgentStep(step="think", thought="鍒嗘瀽鐢ㄦ埛杈撳叆骞跺喅瀹氭槸鍚﹁皟鐢ㄥ伐鍏?)]
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
        steps.append(AgentStep(step="final", thought="鍩轰簬宸ュ叿缁撴灉鍜屼笂涓嬫枃缁欏嚭鏈€缁堢瓟澶?))
        return answer, steps

    def _pick_tool(self, text: str, allowed_tools: set[str]) -> tuple[str | None, str]:
        clean = text.strip()
        if clean.lower().startswith("echo ") and "echo" in allowed_tools:
            return "echo", clean[5:].strip()

        if ("鏃堕棿" in clean or "time" in clean.lower()) and "current_time" in allowed_tools:
            return "current_time", ""

        if "calculator" in allowed_tools and MATH_PATTERN.fullmatch(clean):
            return "calculator", clean

        return None, ""

    async def _final_answer(self, agent: Agent, user_input: str, observation: str | None) -> str:
        system = agent.system_prompt or "浣犳槸涓€涓墽琛屼换鍔＄殑鏅鸿兘浣擄紝璇风粰鍑虹畝娲佸噯纭殑鍥炵瓟銆?
        messages = [{"role": "system", "content": system}]
        if observation is not None:
            messages.append(
                {
                    "role": "system",
                    "content": f"宸ュ叿璋冪敤缁撴灉锛歿observation}銆傝缁撳悎缁撴灉鍥炵瓟鐢ㄦ埛锛屼笉瑕佺紪閫犮€?,
                }
            )
        messages.append({"role": "user", "content": user_input})

        try:
            result = await chat_completion(messages=messages, model=agent.model)
            return result["content"]
        except Exception:
            if observation is not None:
                return f"宸ュ叿鎵ц瀹屾垚锛岀粨鏋滐細{observation}"
            return "鎵ц瀹屾垚锛屼絾褰撳墠妯″瀷涓嶅彲鐢紝璇锋鏌?LLM 閰嶇疆鍚庨噸璇曘€?

