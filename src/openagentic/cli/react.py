"""模块说明（中文）：`src/openagentic/cli/react.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from openagentic.cli._patchable_stdout import _patchable_stdout

from openagentic.cli.llm import litellm_chat
from openagentic.cli.tools import TOOLS, ConfirmFn, execute_tool
from openagentic.config import SETTINGS
from openagentic.memory.manager import (
    MemoryManager,
    working_memory_compressible,
    compress_working_memory,
)

logger = logging.getLogger(__name__)
_console = Console(file=_patchable_stdout)

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _ensure_tool_call_id(tc: dict[str, Any], assistant_msg: dict[str, Any]) -> str:
    """生成并回填 tool_call.id，兼容某些模型（如部分 DeepSeek/OpenAI 兼容端点）
    在 tool_call 中不返回 id 的情况。同步更新 assistant_msg.tool_calls 中
    对应条目的 id，确保后续消息的 tool_call_id 与 assistant 消息匹配。"""
    new_id = f"call_{uuid.uuid4().hex[:24]}"
    tc["id"] = new_id
    for entry in assistant_msg.get("tool_calls", []) or []:
        if entry is tc or (
            entry.get("function", {}).get("name") == tc.get("function", {}).get("name")
            and not entry.get("id")
        ):
            entry["id"] = new_id
    logger.warning("tool_call missing id, generated fallback %s", new_id)
    return new_id


_CUU = "\x1b[F"  # cursor up one line
_EL = "\x1b[K"   # erase to end of line


async def _spin_while(coro, text: str = "思考中..."):
    """Await *coro* while animating a braille spinner.

    Uses cursor-up / erase-to-EOL escapes to overwrite the previous frame
    in-place instead of adding a new line on every frame.  This keeps the
    prompt at the bottom of the terminal even under ``patch_stdout()``.
    """
    done = False
    first_frame = True

    async def _spin() -> None:
        nonlocal first_frame
        i = 0
        while not done:
            frame = _SPINNER[i % len(_SPINNER)]
            if first_frame:
                sys.stdout.write(f"  {frame} {text}\n")
                first_frame = False
            else:
                sys.stdout.write(f"{_CUU}{_EL}  {frame} {text}\n")
            sys.stdout.flush()
            await asyncio.sleep(0.08)
            i += 1
        if not first_frame:
            sys.stdout.write(f"{_CUU}{_EL}")
            sys.stdout.flush()

    task = asyncio.create_task(_spin())
    try:
        return await coro
    finally:
        done = True
        await task


async def react_loop(
    user_input: str,
    messages: list[dict[str, Any]],
    model: str,
    api_base: str | None,
    api_key: str | None,
    *,
    platform_api_base: str | None = None,
    platform_user_email: str | None = None,
    confirm_fn: ConfirmFn | None = None,
) -> str:
    """Run the ReAct loop: Thought → Action → Observation → ... → done."""
    base = (platform_api_base or "").strip()
    if base and not (platform_user_email or "").strip():
        msg = (
            "[平台] 已配置 OpenAgentic 服务地址，但未登录，ReAct 代理不会调用大模型。"
            "请先执行 `/login-platform` 完成注册或登录（与 LLM 厂商 Key 无关），再发任务。"
        )
        _console.print(f"\n[yellow]{msg}[/yellow]")
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": msg})
        return msg

    messages.append({"role": "user", "content": user_input})

    # ── Episodic memory injection: search past episodes relevant to user_input ──
    try:
        eps = MemoryManager().search_episodes(user_input, top_k=3)
        if eps:
            ctx = "## Relevant Past Experiences\n\n"
            for i, ep in enumerate(eps, 1):
                ctx += f"{i}. {ep['title']}\n   {ep['summary'][:300]}\n\n"
            messages.insert(1, {"role": "system", "content": ctx})
    except Exception as exc:
        logger.warning("episodic memory injection failed: %s", exc, exc_info=True)

    # ── Procedural memory injection: search reusable procedures matching user_input ──
    try:
        procs = MemoryManager().search_procedures(user_input, top_k=3)
        if procs:
            ctx = "## Relevant Procedures\n\n"
            for i, p in enumerate(procs, 1):
                ctx += f"{i}. {p['name']}\n   {p['content'][:300]}\n\n"
            messages.insert(1, {"role": "system", "content": ctx})
    except Exception as exc:
        logger.warning("procedural memory injection failed: %s", exc, exc_info=True)

    # ── Working memory compression: compress if over token budget ──
    if working_memory_compressible(messages):
        try:
            messages[:] = await compress_working_memory(
                messages,
                model=model,
                api_base=api_base,
                api_key=api_key,
            )
        except Exception as exc:
            logger.warning("working memory compression failed: %s", exc, exc_info=True)

    last_tool_name = ""
    last_result_preview = ""

    max_iter = max(1, SETTINGS.CLI_REACT_MAX_ITERATIONS)

    for i in range(max_iter):
        if max_iter > 10 and i == max_iter - 6:
            _console.print(
                f"[yellow]已接近单轮工具循环上限（{max_iter}），"
                "若仍无终答将自动停止并给出明确说明。[/yellow]"
            )

        resp = await _spin_while(
            litellm_chat(messages, model, api_base=api_base, api_key=api_key, tools=TOOLS),
            text="思考中...",
        )
        msg = resp.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        thinking = msg.get("thinking", "")

        if thinking:
            lines = thinking.strip().split("\n")
            if len(lines) > 3:
                _console.print(f"  [dim]⏺ {lines[0]}...[/dim]")
            else:
                for line in lines:
                    _console.print(f"  [dim]⏺ {line}[/dim]")

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

            _console.print(f"  [cyan]✦ {name}[/cyan]")

            if name == "done":
                summary = args.get("summary", content or "Done.")
                _console.print()
                _console.print(Markdown(summary))
                tid_done = tc.get("id") or _ensure_tool_call_id(tc, assistant_msg)
                messages.append({"role": "tool", "tool_call_id": tid_done, "content": summary})
                return summary

            result = await execute_tool(name, args, confirm_fn=confirm_fn)
            last_tool_name = name
            last_result_preview = (result or "")[:400].replace("\n", " ")
            _console.print(f"  [dim]{result[:500]}[/dim]")

            tid = tc.get("id") or _ensure_tool_call_id(tc, assistant_msg)
            tool_msg: dict = {"role": "tool", "content": result, "tool_call_id": tid}
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
    _console.print(Panel(Markdown(conclusion), title="ReAct 循环上限", border_style="yellow"))
    messages.append({"role": "assistant", "content": conclusion})
    return conclusion
