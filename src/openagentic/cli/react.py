"""模块说明（中文）：`src/openagentic/cli/react.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from openagentic.cli.llm import litellm_chat
from openagentic.cli.tools import TOOLS, execute_tool
from openagentic.config import SETTINGS

_console = Console()


async def react_loop(
    user_input: str,
    messages: list[dict[str, Any]],
    model: str,
    api_base: str | None,
    api_key: str | None,
    *,
    platform_api_base: str | None = None,
    platform_user_email: str | None = None,
) -> str:
    """Run the ReAct loop: Thought → Action → Observation → ... → done."""
    base = (platform_api_base or "").strip()
    if base and not (platform_user_email or "").strip():
        msg = (
            "[平台] 已配置 OpenAgentic 服务地址，但未登录，ReAct 代理不会调用大模型。"
            "请先执行 `/login-platform` 完成注册或登录（与 LLM 厂商 Key 无关），再发任务。"
        )
        print(f"\n\033[33m{msg}\033[0m")
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": msg})
        return msg

    messages.append({"role": "user", "content": user_input})

    last_tool_name = ""
    last_result_preview = ""

    max_iter = max(1, SETTINGS.CLI_REACT_MAX_ITERATIONS)

    for i in range(max_iter):
        if max_iter > 10 and i == max_iter - 6:
            _console.print(
                f"\n[yellow][提示] 已接近单轮工具循环上限（{max_iter}），"
                "若仍无终答将自动停止并给出明确说明。[/yellow]"
            )

        resp = await litellm_chat(messages, model, api_base=api_base, api_key=api_key, tools=TOOLS)
        msg = resp.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        thinking = msg.get("thinking", "")

        if thinking:
            lines = thinking.strip().split("\n")
            if len(lines) > 3:
                _console.print(f"  [dim][thinking] {lines[0]}... ({len(lines)} lines)[/dim]")
            else:
                for line in lines:
                    _console.print(f"  [dim][thinking] {line}[/dim]")

        if not tool_calls:
            if content:
                _console.print()
                _console.print(Markdown(content))
            final_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if thinking:
                final_msg["reasoning_content"] = thinking
            messages.append(final_msg)
            return content

        assistant_msg: dict[str, Any] = {
            "role": msg["role"],
            "content": msg.get("content"),
            "tool_calls": msg["tool_calls"],
        }
        if thinking:
            assistant_msg["reasoning_content"] = thinking
        messages.append(assistant_msg)

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)

            _console.print(f"\n  [cyan][tool: {name}][/cyan]")

            if name == "done":
                summary = args.get("summary", content or "Done.")
                _console.print()
                _console.print(Markdown(summary))
                tid_done = tc.get("id")
                if not tid_done:
                    raise RuntimeError("模型返回的 tool_call 缺少 id，无法对接 DeepSeek/OpenAI 兼容 API")
                messages.append({"role": "tool", "tool_call_id": tid_done, "content": summary})
                return summary

            result = execute_tool(name, args)
            last_tool_name = name
            last_result_preview = (result or "")[:400].replace("\n", " ")
            _console.print(f"  [dim]{result[:500]}[/dim]")

            tool_msg: dict = {"role": "tool", "content": result}
            tid = tc.get("id")
            if not tid:
                raise RuntimeError("模型返回的 tool_call 缺少 id，无法对接 DeepSeek/OpenAI 兼容 API")
            tool_msg["tool_call_id"] = tid
            messages.append(tool_msg)

    conclusion = (
        f"本轮「模型 ↔ 工具」循环已达到上限（共 {max_iter} 轮），已自动停止，避免死循环或无限消耗 token。\n\n"
        "**结论**：模型未在限制内给出纯文本终答，也未调用 `done` 工具收尾，因此无法判定任务已完整完成。\n"
    )
    if last_tool_name:
        conclusion += f"**最后执行的工具**：`{last_tool_name}`\n"
    if last_result_preview:
        conclusion += f"**该步输出摘要（截断）**：{last_result_preview}\n"
    conclusion += (
        "\n**建议你**：① 查看上方各步工具输出自行判断进度；② 把需求拆小后重试；"
        "③ 下一条消息要求模型「先用一段话总结当前进度与缺口，不要继续调工具」。"
    )
    _console.print()
    _console.print(Panel(Markdown(conclusion), title="[red]已达 ReAct 循环上限[/red]", border_style="yellow"))
    messages.append({"role": "assistant", "content": conclusion})
    return conclusion
