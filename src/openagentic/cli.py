"""OpenAgentic CLI — ReAct Agent with tool calling via Ollama/OpenAI-compatible APIs."""

import argparse
import readline  # noqa: F401 — enables arrow keys + history in input()
import asyncio
import json
import os
import re
import subprocess
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "qwen3:14b"
OLLAMA_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
IDENTITY_QUESTION_RE = re.compile(
    r"(你背后|你用的|什么模型|哪个模型|provider|底层模型|大模型|what model|which model|model provider)",
    re.IGNORECASE,
)

# ── Tool definitions (sent to LLM) ──────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command on the server and return stdout/stderr. Use for: listing files, checking system status, running scripts, git operations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (e.g. 'ls -la /opt', 'df -h', 'cat file.txt')",
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
            "description": "Write content to a file (creates or overwrites). Use when you need to create or modify files.",
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
            "name": "done",
            "description": "Call this when the task is fully completed and you want to present the final answer to the user.",
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

# ── Tool execution ──────────────────────────────────────────────────

MAX_OUTPUT = 4000  # truncate long outputs


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
            with open(path, "r") as f:
                content = f.read()
            if len(content) > MAX_OUTPUT:
                content = content[:MAX_OUTPUT] + f"\n... (truncated, {len(content)} chars total)"
            return content or "(empty file)"

        elif name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            print(f"  \033[33m[write] {path} ({len(content)} chars)\033[0m")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"OK: wrote {len(content)} chars to {path}"

        elif name == "done":
            return args.get("summary", "")

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"


# ── Model API clients ───────────────────────────────────────────────

def resolve_provider(provider: str) -> str:
    """Resolve provider from explicit value or environment."""
    if provider in {"ollama", "openai"}:
        return provider
    if OPENAI_API_KEY:
        return "openai"
    return "ollama"


def normalize_openai_message(message: dict) -> dict:
    """Normalize OpenAI chat message shape for local loop processing."""
    role = message.get("role", "assistant")
    content = message.get("content")
    if content is None:
        content = ""
    return {
        "role": role,
        "content": content,
        "tool_calls": message.get("tool_calls", []),
    }


def is_identity_question(text: str) -> bool:
    return bool(IDENTITY_QUESTION_RE.search(text))


def build_identity_answer(provider: str, model: str, endpoint: str) -> str:
    return (
        "当前运行时配置如下：\n"
        f"- provider: {provider}\n"
        f"- model: {model}\n"
        f"- endpoint: {endpoint}\n\n"
        "我只会按这里的实时配置回答，不会引用其它默认话术。"
    )


async def ollama_chat(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
) -> dict:
    """Call Ollama /api/chat (non-streaming for tool loop)."""
    payload = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=300, proxy=None) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


async def openai_chat(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
) -> dict:
    """Call OpenAI-compatible /chat/completions endpoint."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=300, proxy=None) as client:
        resp = await client.post(f"{OPENAI_BASE}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices", [])
    if not choices:
        return {"message": {"role": "assistant", "content": ""}}
    raw_msg = choices[0].get("message", {})
    return {"message": normalize_openai_message(raw_msg)}


# ── ReAct loop ──────────────────────────────────────────────────────

MAX_ITERATIONS = 15


async def react_loop(
    user_input: str,
    messages: list[dict],
    model: str,
    provider: str,
) -> str:
    """Run the ReAct loop: Thought → Action → Observation → ... → done."""
    messages.append({"role": "user", "content": user_input})

    for i in range(MAX_ITERATIONS):
        # Call LLM with tools
        if provider == "openai":
            resp = await openai_chat(messages, model, tools=TOOLS)
        else:
            resp = await ollama_chat(messages, model, tools=TOOLS)
        msg = resp.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        thinking = msg.get("thinking", "")

        # Show thinking if present
        if thinking:
            # Show abbreviated thinking
            lines = thinking.strip().split("\n")
            if len(lines) > 3:
                print(f"  \033[2m[thinking] {lines[0]}... ({len(lines)} lines)\033[0m")
            else:
                for line in lines:
                    print(f"  \033[2m[thinking] {line}\033[0m")

        # No tool calls — LLM is giving a direct answer
        if not tool_calls:
            if content:
                print(f"\n\033[32m{content}\033[0m")
            messages.append({"role": "assistant", "content": content})
            return content

        # Execute each tool call
        messages.append(msg)  # assistant message with tool_calls

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)

            print(f"\n  \033[36m[tool: {name}]\033[0m")

            # done tool — final answer
            if name == "done":
                summary = args.get("summary", content or "Done.")
                print(f"\n\033[32m{summary}\033[0m")
                messages.append({"role": "tool", "content": summary})
                return summary

            # Execute and feed back
            result = execute_tool(name, args)
            print(f"  \033[2m{result[:500]}\033[0m")

            tool_msg = {"role": "tool", "content": result}
            if tc.get("id"):
                tool_msg["tool_call_id"] = tc["id"]
            messages.append(tool_msg)

    print("\n\033[31m[max iterations reached]\033[0m")
    return "(max iterations)"


# ── Main REPL ───────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are OpenAgentic, an AI agent running on a Linux server. You can execute shell commands, read/write files to accomplish tasks.

Runtime identity (MUST be truthful):
- provider: {provider}
- model: {model}
- endpoint: {endpoint}

Rules:
1. Think step by step about what needs to be done.
2. Use tools to gather information and take actions.
3. After completing the task, call the `done` tool with a summary.
4. If the user asks a simple question that doesn't need tools, answer directly without calling any tool.
5. Be careful with destructive operations (rm -rf, etc.) — confirm intent first.
6. Keep command outputs concise; use head/tail/grep when appropriate.
7. If user asks what model/provider you are using, answer strictly from runtime identity above.
8. Never claim a different vendor/model (e.g., Claude/OpenAI/DeepSeek) unless it matches runtime identity."""


async def main_loop(model: str, provider: str, system_prompt: str | None = None):
    provider = resolve_provider(provider)
    if provider == "openai" and model == DEFAULT_MODEL:
        model = OPENAI_CHAT_MODEL
    messages: list[dict] = []
    endpoint = OPENAI_BASE if provider == "openai" else OLLAMA_BASE
    default_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        provider=provider,
        model=model,
        endpoint=endpoint,
    )
    sp = system_prompt or default_prompt
    messages.append({"role": "system", "content": sp})

    print(f"\033[1mOpenAgentic Agent\033[0m  |  provider: {provider}  |  model: {model}")
    print(f"Tools: run_command, read_file, write_file")
    print("Commands: /clear /model <name> /quit")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n\033[1m> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("Bye!")
            break
        if user_input == "/clear":
            messages = [messages[0]]  # keep system prompt
            print("[history cleared]")
            continue
        if user_input.startswith("/model "):
            model = user_input[7:].strip()
            print(f"[model → {model}]")
            continue
        if is_identity_question(user_input):
            identity_answer = build_identity_answer(provider, model, endpoint)
            print(f"\n\033[32m{identity_answer}\033[0m")
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": identity_answer})
            continue

        try:
            await react_loop(user_input, messages, model, provider)
        except httpx.ConnectError:
            if provider == "openai":
                print(f"\033[31m[ERROR] Cannot connect to OpenAI-compatible endpoint at {OPENAI_BASE}\033[0m")
            else:
                print(f"\033[31m[ERROR] Cannot connect to Ollama at {OLLAMA_BASE}\033[0m")
        except Exception as e:
            print(f"\033[31m[ERROR] {type(e).__name__}: {e}\033[0m")


def main():
    parser = argparse.ArgumentParser(description="OpenAgentic Agent CLI (ReAct)")
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL}; OpenAI mode uses OPENAI_CHAT_MODEL when unchanged)",
    )
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "ollama", "openai"],
        help="LLM provider: auto/ollama/openai-compatible",
    )
    parser.add_argument("-s", "--system", default=None, help="Custom system prompt")
    args = parser.parse_args()
    asyncio.run(main_loop(args.model, args.provider, args.system))


if __name__ == "__main__":
    main()
