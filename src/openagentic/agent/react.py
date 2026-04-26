"""模块说明（中文）：`src/openagentic/agent/react.py`。

ReAct（Reasoning + Acting）执行器：在「思考→选工具→执行→最终回答」的
循环中完成单轮 Agent 任务。当前为简化版 ReAct，不涉及多轮迭代。
"""

from __future__ import annotations

import re

from openagentic.agent.models import Agent
from openagentic.agent.tools import ToolRegistry
from openagentic.core.llm.service import chat_completion

# 匹配纯数学表达式（数字/运算符/括号/空格），用于自动路由到 calculator 工具
MATH_PATTERN = re.compile(r"[-+*/().\d\s]{3,}")


class ReactExecutor:
    """简化版 ReAct 执行器：一轮「思考→选工具→执行→最终回答」。

    当前不循环多轮——若需多轮 ReAct，在调用方做 while loop。
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def run(self, agent: Agent, user_input: str) -> tuple[str, list[dict]]:
        """执行单轮 ReAct：选工具 → 调用 → LLM 最终回答。

        Returns:
            (最终回答文本, 步骤追踪列表)
        """
        # 步骤追踪：供前端/API 展示执行过程
        steps: list[dict] = [{"step": "think", "thought": "分析用户输入并决定是否调用工具"}]
        allowed_tools = set(agent.tools or [])

        # 第一步：尝试从用户输入中自动识别工具调用意图
        tool_name, tool_arg = self._pick_tool(user_input, allowed_tools)
        observation = None
        if tool_name:
            try:
                # 同步执行工具（仅支持 legacy 同步工具；async 工具走 function-calling 路径）
                observation = self.registry.call(tool_name, tool_arg)
                steps.append(
                    {"step": "act", "action": f"{tool_name}({tool_arg})", "observation": observation}
                )
            except ValueError as exc:
                steps.append({"step": "act", "action": tool_name, "observation": str(exc)})

        # 第二步：把工具结果（如有）连同用户输入，交给 LLM 生成最终回答
        answer = await self._final_answer(agent, user_input, observation)
        steps.append({"step": "final", "thought": "基于工具结果和上下文给出最终答复"})
        return answer, steps

    def _pick_tool(self, text: str, allowed_tools: set[str]) -> tuple[str | None, str]:
        """基于规则匹配用户输入，自动选择工具（不依赖 LLM function-calling）。

        当前只做简单关键词/模式匹配，未来可扩展为分类器。
        """
        clean = text.strip()

        # echo 命令显式调用
        if clean.lower().startswith("echo ") and "echo" in allowed_tools:
            return "echo", clean[5:].strip()

        # 时间查询（中英文触发词）
        if ("时间" in clean or "time" in clean.lower()) and "current_time" in allowed_tools:
            return "current_time", ""

        # 纯数学表达式 → calculator
        if "calculator" in allowed_tools and MATH_PATTERN.fullmatch(clean):
            return "calculator", clean

        return None, ""

    async def _final_answer(self, agent: Agent, user_input: str, observation: str | None) -> str:
        """用 LLM 生成最终回答，注入 agent 的 system prompt 和工具结果上下文。

        若 LLM 不可用，降级返回工具观察结果或错误提示。
        """
        system = agent.system_prompt or "你是一个执行任务的智能体，请给出简洁准确的回答。"
        messages = [{"role": "system", "content": system}]

        # 工具结果作为额外的 system 消息注入，引导 LLM 结合结果回答
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
            # LLM 不可用时降级返回工具结果或错误提示
            if observation is not None:
                return f"工具执行完成，结果：{observation}"
            return "执行完成，但当前模型不可用，请检查 LLM 配置后重试。"
