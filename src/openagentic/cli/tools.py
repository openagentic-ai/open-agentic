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
    """Interactive yes/no; non-TTY or cancel 鈫?False (Claude-style gate)."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    print(f"\n\033[33m[闇€瑕佺‘璁 {title}\033[0m")
    print(detail)
    try:
        ans = input("纭缁х画? (Y/N): ").strip().lower()
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
                return f"[ERROR] write_file: 璺緞鏄洰褰曪紝璇锋寚瀹氬叿浣撴枃浠惰矾寰? {p}"
            exists = p.is_file()
            op_label = "瑕嗙洊宸叉湁鏂囦欢" if exists else "鏂板缓鏂囦欢锛堝鍔犳枃浠讹級"
            title = "瑕嗙洊鍐欏叆鏂囦欢" if exists else "鏂板缓鏂囦欢"
            preview = f"璺緞: {p}\n瀛楄妭鏁? {len(content.encode('utf-8'))}\n鎿嶄綔: {op_label}"
            if not confirm_user_action(title, preview):
                return "[REFUSED] 鐢ㄦ埛鏈‘璁ゅ啓鍏ワ紝宸插彇娑堬紙鍙敤鑷劧璇█璇存槑濡備綍鎵嬪姩淇敼锛?
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
                return f"[ERROR] delete_file: 涓嶆槸鏅€氭枃浠舵垨涓嶅瓨鍦? {p}"
            if not confirm_user_action("鍒犻櫎鏂囦欢", f"璺緞: {p}\n姝ゆ搷浣滀笉鍙挙閿€"):
                return "[REFUSED] 鐢ㄦ埛鏈‘璁ゅ垹闄わ紝宸插彇娑?
            print(f"  \033[33m[delete] {p}\033[0m")
            p.unlink()
            return f"OK: deleted file {p}"

        elif name == "done":
            return args.get("summary", "")

        return f"Unknown tool: {name}"

    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"
