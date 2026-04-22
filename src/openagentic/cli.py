"""OpenAgentic CLI — ReAct Agent with multi-provider model selection."""

import argparse
import readline  # noqa: F401 — enables arrow keys + history in input()
import asyncio
import json
import os
import re
import subprocess

import litellm
from dotenv import load_dotenv

from openagentic.core.llm.provider_config import get_provider_store

load_dotenv()

DEFAULT_MODEL = "qwen3:14b"
IDENTITY_QUESTION_RE = re.compile(
    r"(你背后|你用的|什么模型|哪个模型|provider|底层模型|大模型|what model|which model|model provider)",
    re.IGNORECASE,
)
PROVIDER_ALIASES = {
    "claude": "anthropic",
    "anthropic": "anthropic",
    "openai": "openai",
    "grok": "xai",
    "xai": "xai",
    "gemini": "gemini",
    "deepseek": "deepseek",
    "qwen": "qwen",
    "ollama": "ollama",
}

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

def normalize_provider(provider: str) -> str:
    lower = provider.strip().lower()
    return PROVIDER_ALIASES.get(lower, lower)


def list_provider_profiles() -> list[dict]:
    config = get_provider_store().get()
    profiles = []
    for profile in config.profiles:
        profiles.append(
            {
                "id": profile.id,
                "display_name": profile.display_name,
                "api_base": profile.api_base,
                "api_key": profile.api_key,
                "models": profile.models,
                "enabled": profile.enabled,
            }
        )
    return profiles


def find_profile(provider: str) -> dict | None:
    provider = normalize_provider(provider)
    for profile in list_provider_profiles():
        if profile["id"] == provider:
            return profile
    return None


def resolve_provider(provider: str, model: str) -> str:
    if provider and provider != "auto":
        return normalize_provider(provider)
    if "/" in model:
        return normalize_provider(model.split("/", 1)[0])
    default_model = get_provider_store().get().default_model
    if "/" in default_model:
        return normalize_provider(default_model.split("/", 1)[0])
    return "ollama"


def resolve_model_for_provider(provider: str, model: str) -> str:
    if model and model != DEFAULT_MODEL:
        if "/" in model:
            model_provider = normalize_provider(model.split("/", 1)[0])
            if model_provider == provider:
                return model
        return f"{provider}/{model}"
    profile = find_profile(provider)
    if profile and profile["models"]:
        return profile["models"][0]
    return get_provider_store().get().default_model


def require_provider_configured(provider: str) -> tuple[str, str | None]:
    profile = find_profile(provider)
    if not profile:
        raise RuntimeError(f"Unknown provider: {provider}")
    if not profile["enabled"]:
        raise RuntimeError(f"Provider {provider} is disabled. Please enable it in config.")
    if provider != "ollama" and not profile["api_key"]:
        configure_provider_interactive(provider)
        profile = find_profile(provider)
        if not profile:
            raise RuntimeError(f"Unknown provider: {provider}")
    api_base = profile["api_base"] or None
    api_key = profile["api_key"] or None
    if provider != "ollama" and not api_key:
        raise RuntimeError(f"Provider {provider} requires API key before use.")
    return api_base or "", api_key


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


async def litellm_chat(
    messages: list[dict],
    model: str,
    api_base: str | None,
    api_key: str | None,
    tools: list[dict] | None = None,
) -> dict:
    """Call model via LiteLLM with optional tool calling."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "api_base": api_base or None,
        "api_key": api_key or None,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    msg = choice.message
    tool_calls = []
    for tc in (getattr(msg, "tool_calls", None) or []):
        args = tc.function.arguments if getattr(tc, "function", None) else "{}"
        tool_calls.append(
            {
                "id": getattr(tc, "id", None),
                "function": {
                    "name": tc.function.name if getattr(tc, "function", None) else "",
                    "arguments": args,
                },
            }
        )
    return {
        "message": {
            "role": getattr(msg, "role", "assistant"),
            "content": getattr(msg, "content", "") or "",
            "tool_calls": tool_calls,
        }
    }


def print_provider_menu(current_provider: str) -> None:
    print("\n可选模型厂商：")
    for profile in list_provider_profiles():
        mark = "*" if profile["id"] == current_provider else " "
        status = "enabled" if profile["enabled"] else "disabled"
        key_status = "key:yes" if profile["api_key"] else "key:no"
        print(f" {mark} {profile['id']:<10} {profile['display_name']:<18} [{status}, {key_status}]")


def configure_provider_interactive(provider: str) -> None:
    provider = normalize_provider(provider)
    profile = find_profile(provider)
    if profile is None:
        print(f"[ERROR] 未找到 provider: {provider}")
        return
    print(f"\n--- 配置 {profile['display_name']} ({provider}) ---")
    current_base = profile["api_base"] or ""
    current_models = ", ".join(profile["models"] or [])
    api_base = input(f"API Base [{current_base}]: ").strip() or current_base
    api_key = input("API Key（留空保持不变）: ").strip()
    models_input = input(f"模型列表(逗号分隔) [{current_models}]: ").strip()
    enabled_input = input(f"启用? (y/n) [{'y' if profile['enabled'] else 'n'}]: ").strip().lower()
    enabled = profile["enabled"] if enabled_input == "" else enabled_input in {"y", "yes", "1"}
    models = (
        [m.strip() for m in models_input.split(",") if m.strip()]
        if models_input
        else profile["models"]
    )
    get_provider_store().upsert_profile(
        provider,
        api_base=api_base,
        api_key=api_key if api_key else None,
        models=models,
        enabled=enabled,
    )
    print(f"[OK] 已保存 {provider} 配置")


# ── ReAct loop ──────────────────────────────────────────────────────

MAX_ITERATIONS = 15


async def react_loop(
    user_input: str,
    messages: list[dict],
    model: str,
    api_base: str | None,
    api_key: str | None,
) -> str:
    """Run the ReAct loop: Thought → Action → Observation → ... → done."""
    messages.append({"role": "user", "content": user_input})

    for i in range(MAX_ITERATIONS):
        # Call LLM with tools
        resp = await litellm_chat(messages, model, api_base=api_base, api_key=api_key, tools=TOOLS)
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
    provider = resolve_provider(provider, model)
    model = resolve_model_for_provider(provider, model)
    api_base, api_key = require_provider_configured(provider)
    messages: list[dict] = []
    endpoint = api_base or "(provider default)"
    default_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        provider=provider,
        model=model,
        endpoint=endpoint,
    )
    sp = system_prompt or default_prompt
    messages.append({"role": "system", "content": sp})

    print(f"\033[1mOpenAgentic Agent\033[0m  |  provider: {provider}  |  model: {model}")
    print("Tools: run_command, read_file, write_file")
    print("Commands: /clear /model <name> /providers /provider <id> /provider-config [id] /quit")
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
            model = resolve_model_for_provider(provider, user_input[7:].strip())
            print(f"[model → {model}]")
            continue
        if user_input == "/providers":
            print_provider_menu(provider)
            continue
        if user_input.startswith("/provider "):
            selected = normalize_provider(user_input[10:].strip())
            if not find_profile(selected):
                print(f"[ERROR] 未知 provider: {selected}")
                continue
            provider = selected
            configure_provider_interactive(provider)
            api_base, api_key = require_provider_configured(provider)
            model = resolve_model_for_provider(provider, model)
            endpoint = api_base or "(provider default)"
            messages[0] = {
                "role": "system",
                "content": SYSTEM_PROMPT_TEMPLATE.format(
                    provider=provider,
                    model=model,
                    endpoint=endpoint,
                ),
            }
            print(f"[provider → {provider}] [model → {model}]")
            continue
        if user_input.startswith("/provider-config"):
            target = user_input.replace("/provider-config", "", 1).strip() or provider
            configure_provider_interactive(target)
            if target == provider:
                api_base, api_key = require_provider_configured(provider)
                endpoint = api_base or "(provider default)"
            continue
        if is_identity_question(user_input):
            identity_answer = build_identity_answer(provider, model, endpoint)
            print(f"\n\033[32m{identity_answer}\033[0m")
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": identity_answer})
            continue

        try:
            await react_loop(user_input, messages, model, api_base, api_key)
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
        help="LLM provider id (auto/openai/anthropic/xai/gemini/deepseek/qwen/ollama)",
    )
    parser.add_argument("-s", "--system", default=None, help="Custom system prompt")
    args = parser.parse_args()
    asyncio.run(main_loop(args.model, args.provider, args.system))


if __name__ == "__main__":
    main()
