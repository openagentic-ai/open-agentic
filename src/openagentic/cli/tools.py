"""模块说明（中文）：`src/openagentic/cli/tools.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine

from rich.console import Console

from openagentic.memory.manager import MemoryManager

_tools_console = Console()

_memory_manager: MemoryManager | None = None

MAX_OUTPUT = 4000  # truncate long outputs


def _get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command on the user's machine (host default shell) and return "
                "stdout/stderr. Use for: listing files, checking system status, running scripts, "
                "git operations, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command for this OS (e.g. Unix: ls, cat; Windows: dir, type)",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full content of a file. Use when you need to inspect a file's content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create a new file or overwrite an existing file. The user must confirm in the "
                "terminal for both cases (new file and overwrite)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a single file (not a directory). The user must confirm before deletion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to delete",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": (
                "Call this when the task is fully completed and you want to present the final answer to the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Final answer / summary for the user",
                    }
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "core_memory_save",
            "description": (
                "Save a fact, preference, or piece of information about the user or project "
                "into persistent core memory. Category must be: user_profile, project_fact, "
                "preference, or reference. Importance 0.0-1.0 helps rank entries. "
                "Use this whenever you learn something worth remembering across sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short unique key (e.g. 'preferred_language', 'project_path')",
                    },
                    "value": {
                        "type": "string",
                        "description": "The information to remember",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["user_profile", "project_fact", "preference", "reference"],
                        "description": "Memory category",
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance 0.0-1.0, default 0.5. Higher = more likely to be injected into future prompts.",
                    },
                },
                "required": ["key", "value", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "core_memory_delete",
            "description": "Delete a core memory entry by its key name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key name of the memory to delete",
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "core_memory_search",
            "description": "Search the user's persistent core memories by keyword. Returns matching entries that may help personalize responses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to match against keys and values",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional filter: user_profile, project_fact, preference, or reference",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results, default 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "episodic_search",
            "description": "Search past conversation episodes and task summaries. Returns relevant past experiences to help with the current task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query describing what past experience to recall",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of past episodes to recall, default 3",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "episodic_save",
            "description": "Save a summary of the current conversation or task as an episodic memory for future recall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for this episode",
                    },
                    "summary": {
                        "type": "string",
                        "description": "3-5 sentence summary of what was accomplished and key outcomes",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords for future search (e.g. ['debug', 'deployment'])",
                    },
                },
                "required": ["title", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "procedural_save",
            "description": "Save a reusable procedure or workflow learned from a successful task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short name for this procedure",
                    },
                    "description": {
                        "type": "string",
                        "description": "What this procedure accomplishes",
                    },
                    "trigger_pattern": {
                        "type": "string",
                        "description": "When to suggest this procedure (natural language description)",
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of steps to execute this procedure",
                    },
                },
                "required": ["name", "description", "trigger_pattern", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "procedural_search",
            "description": "Search for previously saved procedures that match the current task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Description of the current task to match procedures against",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of matching procedures, default 3",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# Type alias for async confirm callback used by the concurrent input queue.
# Signature: async (title, detail) -> bool
ConfirmFn = Callable[[str, str], Coroutine[Any, Any, bool]]


def _default_confirm_sync(title: str, detail: str) -> bool:
    """Fallback interactive yes/no when no async confirm_fn is provided."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    _tools_console.print(f"\n[yellow]确认: {title}[/yellow]")
    print(detail)
    try:
        ans = input("确认继续? (Y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")


def _run_command_sync(cmd: str) -> str:
    """Run a shell command synchronously (called via asyncio.to_thread)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=60,
        encoding="utf-8",
    )
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    output = output.strip()
    if not output:
        output = "(no output)"
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n... (truncated, {len(output)} chars total)"
    if result.returncode != 0:
        output = f"[exit code {result.returncode}]\n{output}"
    return output


async def execute_tool(
    name: str,
    args: dict,
    confirm_fn: ConfirmFn | None = None,
) -> str:
    """Execute a tool and return result string.

    Args:
        confirm_fn: Optional async callable for user confirmation.
                    If None, falls back to synchronous stdin prompt.
    """
    try:
        if name == "run_command":
            cmd = args.get("command", "")
            _tools_console.print(f"  [bold yellow]$[/bold yellow] [dim]{cmd}[/dim]")
            return await asyncio.to_thread(_run_command_sync, cmd)

        elif name == "read_file":
            path = args.get("path", "")
            _tools_console.print(f"  [dim]→ read[/dim] {path}")
            content = await asyncio.to_thread(_read_file_sync, path)
            return content

        elif name == "write_file":
            path = args.get("path", "").strip()
            content = args.get("content", "")
            if not path:
                return "[ERROR] write_file: path is empty"
            p = Path(path).resolve()
            if p.exists() and p.is_dir():
                return f"[ERROR] write_file: 路径是目录，请指定具体文件路径: {p}"
            exists = p.is_file()
            op_label = "覆盖已有文件" if exists else "新建文件（增加文件）"
            title = "覆盖写入文件" if exists else "新建文件"
            preview = f"路径: {p}\n字节数: {len(content.encode('utf-8'))}\n操作: {op_label}"
            if confirm_fn:
                confirmed = await confirm_fn(title, preview)
            else:
                confirmed = _default_confirm_sync(title, preview)
            if not confirmed:
                return "[REFUSED] 用户未确认写入，已取消（可用自然语言说明如何手动修改）"
            _tools_console.print(f"  [dim]→ write[/dim] {p} [dim]({len(content)} chars)[/dim]")
            os.makedirs(str(p.parent), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return f"OK: wrote {len(content)} chars to {p}"

        elif name == "delete_file":
            raw = args.get("path", "").strip()
            if not raw:
                return "[ERROR] delete_file: path is empty"
            p = Path(raw).resolve()
            if not p.is_file():
                return f"[ERROR] delete_file: 不是普通文件或不存在: {p}"
            title = "删除文件"
            detail = f"路径: {p}\n此操作不可撤销"
            if confirm_fn:
                confirmed = await confirm_fn(title, detail)
            else:
                confirmed = _default_confirm_sync(title, detail)
            if not confirmed:
                return "[REFUSED] 用户未确认删除，已取消"
            _tools_console.print(f"  [dim]→ delete[/dim] {p}")
            p.unlink()
            return f"OK: deleted file {p}"

        elif name == "done":
            return args.get("summary", "")

        # ── Memory tools ──
        elif name == "core_memory_save":
            mgr = _get_memory_manager()
            fp = mgr.save_core_memory(
                args["key"],
                args["value"],
                args.get("category", "reference"),
                float(args.get("importance", 0.5)),
            )
            return f"OK: core memory '{args['key']}' saved → {fp}"

        elif name == "core_memory_delete":
            mgr = _get_memory_manager()
            found = mgr.delete_core_memory(args["key"])
            return f"OK: deleted '{args['key']}'" if found else f"NOT FOUND: '{args['key']}'"

        elif name == "core_memory_search":
            mgr = _get_memory_manager()
            results = mgr.search_core(
                args["query"],
                args.get("category"),
                int(args.get("top_k", 5)),
            )
            if not results:
                return "No matching core memories found."
            lines = ["Core memory search results:"]
            for e in results:
                lines.append(f"- [{e.category}] {e.key}: {e.value[:200]}")
            return "\n".join(lines)

        elif name == "episodic_search":
            mgr = _get_memory_manager()
            results = mgr.search_episodes(
                args["query"],
                int(args.get("top_k", 3)),
            )
            if not results:
                return "No matching past episodes found."
            lines = ["Past episode results:"]
            for ep in results:
                lines.append(f"- {ep['title']}: {ep['summary'][:250]}")
            return "\n".join(lines)

        elif name == "episodic_save":
            mgr = _get_memory_manager()
            tags = args.get("tags", [])
            if isinstance(tags, str):
                import json as _json
                tags = _json.loads(tags) if tags.startswith("[") else [tags]
            fp = mgr.save_episode(args["title"], args["summary"], tags)
            return f"OK: episode saved → {fp}"

        elif name == "procedural_save":
            mgr = _get_memory_manager()
            steps = args.get("steps", [])
            if isinstance(steps, str):
                import json as _json
                steps = _json.loads(steps) if steps.startswith("[") else [steps]
            fp = mgr.save_procedure(
                args["name"], args["description"], args["trigger_pattern"], steps,
            )
            return f"OK: procedure '{args['name']}' saved → {fp}"

        elif name == "procedural_search":
            mgr = _get_memory_manager()
            results = mgr.search_procedures(
                args["query"],
                int(args.get("top_k", 3)),
            )
            if not results:
                return "No matching procedures found."
            lines = ["Procedure search results:"]
            for p in results:
                lines.append(f"- {p['name']}: {p['content'][:250]}")
            return "\n".join(lines)

        return f"Unknown tool: {name}"

    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"


def _read_file_sync(path: str) -> str:
    """Read file synchronously (for asyncio.to_thread)."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if len(content) > MAX_OUTPUT:
        content = content[:MAX_OUTPUT] + f"\n... (truncated, {len(content)} chars total)"
    return content or "(empty file)"
