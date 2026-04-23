"""CLI ReAct tool definitions and execution."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT = 4000  # truncate long outputs

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
]


def confirm_user_action(title: str, detail: str) -> bool:
    """Interactive yes/no; non-TTY or cancel → False (Claude-style gate)."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    print(f"\n\033[33m[需要确认] {title}\033[0m")
    print(detail)
    try:
        ans = input("输入 y 或 yes 确认，其它键取消: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return result string."""
    try:
        if name == "run_command":
            cmd = args.get("command", "")
            print(f"  \033[33m$ {cmd}\033[0m")
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60
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

        elif name == "read_file":
            path = args.get("path", "")
            print(f"  \033[33m[read] {path}\033[0m")
            with open(path) as f:
                content = f.read()
            if len(content) > MAX_OUTPUT:
                content = content[:MAX_OUTPUT] + f"\n... (truncated, {len(content)} chars total)"
            return content or "(empty file)"

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
            if not confirm_user_action(title, preview):
                return "[REFUSED] 用户未确认写入，已取消（可用自然语言说明如何手动修改）"
            print(f"  \033[33m[write] {p} ({len(content)} chars)\033[0m")
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
            if not confirm_user_action("删除文件", f"路径: {p}\n此操作不可撤销"):
                return "[REFUSED] 用户未确认删除，已取消"
            print(f"  \033[33m[delete] {p}\033[0m")
            p.unlink()
            return f"OK: deleted file {p}"

        elif name == "done":
            return args.get("summary", "")

        return f"Unknown tool: {name}"

    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"
