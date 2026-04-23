"""OpenAgentic CLI — ReAct Agent with multi-provider model selection."""

import argparse
import asyncio
import json
import os
import platform
from pathlib import Path
import re
import select
import subprocess
import sys
import time

import httpx

try:
    import readline  # noqa: F401  # enables arrow keys + history on Unix-like systems
except ImportError:
    # Windows doesn't ship stdlib readline; CLI can still run without it.
    readline = None  # noqa: F841

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
    "mistral": "mistral",
    "cohere": "cohere",
    "groq": "groq",
    "openrouter": "openrouter",
    "kimi": "moonshot",
    "moonshot": "moonshot",
    "zhipu": "zhipu",
    "zhipuai": "zhipu",
    "glm": "zhipu",
    "minimax": "minimax",
    "doubao": "volcengine",
    "bytedance": "volcengine",
    "volcengine": "volcengine",
    "baidu": "baidu",
    "ernie": "baidu",
    "tencent": "tencent",
    "hunyuan": "tencent",
    "nvidia": "nvidia",
    "together": "together",
    "togetherai": "together",
    "fireworks": "fireworks",
    "qwen": "qwen",
    "ollama": "ollama",
}
KNOWN_PROVIDER_IDS = set(PROVIDER_ALIASES.values()) | {"openai"}
OPENAI_COMPATIBLE_PROVIDERS = {
    "groq",
    "openrouter",
    "moonshot",
    "zhipu",
    "minimax",
    "volcengine",
    "baidu",
    "tencent",
    "nvidia",
    "together",
    "fireworks",
}

# ── Tool definitions (sent to LLM) ──────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command on the user's machine (host default shell) and return stdout/stderr. Use for: listing files, checking system status, running scripts, git operations, etc.",
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
            "description": "Create a new file or overwrite an existing file. The user must confirm in the terminal for both cases (new file and overwrite).",
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
            with open(path, "r") as f:
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

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"


def maybe_auto_install_editable() -> None:
    """Auto-run `pip install -e .` when local source changed."""
    project_root = Path(__file__).resolve().parents[2]
    pyproject = project_root / "pyproject.toml"
    src_dir = project_root / "src"
    stamp_dir = project_root / ".openagentic"
    stamp_file = stamp_dir / ".last_editable_install"

    if not pyproject.exists() or not src_dir.exists():
        return

    latest_mtime = pyproject.stat().st_mtime
    for path in src_dir.rglob("*.py"):
        try:
            latest_mtime = max(latest_mtime, path.stat().st_mtime)
        except OSError:
            continue

    last_installed = 0.0
    if stamp_file.exists():
        try:
            last_installed = float(stamp_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            last_installed = 0.0

    if last_installed >= latest_mtime:
        return

    print("[bootstrap] 检测到本地源码更新，正在执行: pip install -e .")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        cwd=str(project_root),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print("[WARN] 自动安装失败，请手动执行: pip install -e .")
        err = (result.stderr or result.stdout or "").strip()
        if err:
            print(err[:800])
        return

    stamp_dir.mkdir(parents=True, exist_ok=True)
    stamp_file.write_text(str(time.time()), encoding="utf-8")
    print("[bootstrap] 已完成自动安装。")


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
    profile = find_profile(provider)

    if model and model != DEFAULT_MODEL:
        candidate = model.strip()
        if "/" in candidate:
            parts = candidate.split("/")
            model_provider = normalize_provider(parts[0])
            if model_provider == provider:
                # Guard against malformed values like "deepseek/openai/gpt-4.1".
                if len(parts) >= 3 and normalize_provider(parts[1]) in KNOWN_PROVIDER_IDS:
                    if profile and profile["models"]:
                        return profile["models"][0]
                    return get_provider_store().get().default_model
                return candidate
            if provider in OPENAI_COMPATIBLE_PROVIDERS:
                # Keep explicit OpenAI-compatible slugs, e.g. "openai/gpt-4.1" or "anthropic/..."
                return candidate
            # Provider mismatch: prefer provider's own default model.
            if profile and profile["models"]:
                return profile["models"][0]
            return get_provider_store().get().default_model
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            return f"openai/{candidate}"
        return f"{provider}/{candidate}"
    if profile and profile["models"]:
        return profile["models"][0]
    return get_provider_store().get().default_model


def normalize_runtime_model(provider: str, model_name: str) -> str:
    if "/" in model_name:
        return model_name
    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        return f"openai/{model_name}"
    return f"{provider}/{model_name}"


def discover_models_openai_compatible(provider: str, api_base: str, api_key: str) -> list[str]:
    if not api_base or not api_key or provider == "ollama":
        return []
    endpoint = f"{api_base.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = httpx.get(endpoint, headers=headers, timeout=8.0)
        if response.status_code != 200:
            return []
        payload = response.json()
        raw_models = payload.get("data", [])
        ids: list[str] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                ids.append(model_id.strip())

        seen: set[str] = set()
        normalized: list[str] = []
        for model_id in ids:
            runtime_model = normalize_runtime_model(provider, model_id)
            if runtime_model in seen:
                continue
            seen.add(runtime_model)
            normalized.append(runtime_model)
        return normalized
    except Exception:
        return []


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
        f"- host: {runtime_environment_summary()}\n"
        f"- provider: {provider}\n"
        f"- model: {model}\n"
        f"- endpoint: {endpoint}\n"
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
        raw_args = tc.function.arguments if getattr(tc, "function", None) else "{}"
        if isinstance(raw_args, dict):
            args = json.dumps(raw_args, ensure_ascii=False)
        else:
            args = raw_args if isinstance(raw_args, str) else "{}"
        tool_calls.append(
            {
                "id": getattr(tc, "id", None),
                "type": "function",
                "function": {
                    "name": tc.function.name if getattr(tc, "function", None) else "",
                    "arguments": args,
                },
            }
        )
    out_content = getattr(msg, "content", None)
    if tool_calls and (out_content is None or out_content == ""):
        out_content = None
    else:
        out_content = out_content or ""
    return {
        "message": {
            "role": getattr(msg, "role", "assistant"),
            "content": out_content,
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


def read_nav_key() -> str:
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            return "enter"
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "up"
            if ch2 == "P":
                return "down"
            return "other"
        if ch == "\x03":
            return "interrupt"
        if ch in ("\x1b", "q", "Q"):
            return "quit"
        return "other"

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            return "interrupt"
        if ch == "\x1b":
            seq = ""
            if select.select([sys.stdin], [], [], 0.05)[0]:
                seq += sys.stdin.read(1)
            if select.select([sys.stdin], [], [], 0.05)[0]:
                seq += sys.stdin.read(1)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "quit"
        if ch in ("q", "Q"):
            return "quit"
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def select_provider_interactive(current_provider: str) -> str | None:
    profiles = list_provider_profiles()
    if not profiles:
        return None
    ids = [p["id"] for p in profiles]
    selected_idx = ids.index(current_provider) if current_provider in ids else 0

    # Fallback for non-interactive terminals.
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print_provider_menu(current_provider)
        selected = input(f"请选择 provider（默认 {current_provider}）: ").strip()
        return normalize_provider(selected) if selected else current_provider

    while True:
        if os.name == "nt":
            os.system("cls")
        else:
            print("\033[2J\033[H", end="")
        print("可选模型厂商（↑/↓ 选择，Enter 确认，q 取消）：")
        for idx, profile in enumerate(profiles):
            cursor = ">" if idx == selected_idx else " "
            status = "enabled" if profile["enabled"] else "disabled"
            key_status = "key:yes" if profile["api_key"] else "key:no"
            print(
                f" {cursor} {profile['id']:<12} {profile['display_name']:<24} "
                f"[{status}, {key_status}]"
            )

        key = read_nav_key()
        if key == "up":
            selected_idx = (selected_idx - 1) % len(profiles)
            continue
        if key == "down":
            selected_idx = (selected_idx + 1) % len(profiles)
            continue
        if key == "enter":
            return profiles[selected_idx]["id"]
        if key in {"quit", "interrupt"}:
            return None


def looks_like_api_key(value: str) -> bool:
    value = value.strip()
    if not value or " " in value:
        return False
    return value.startswith("sk-") or len(value) >= 24


def configure_provider_interactive(provider: str) -> None:
    provider = normalize_provider(provider)
    profile = find_profile(provider)
    if profile is None:
        print(f"[ERROR] 未找到 provider: {provider}")
        return
    print(f"\n--- 配置 {profile['display_name']} ({provider}) ---")
    print("提示：按回车采用默认项。")
    current_base = profile["api_base"] or ""
    current_models = ", ".join(profile["models"] or [])
    current_key = profile["api_key"] or ""

    # For cloud providers, ask key first to reduce misconfiguration.
    api_key = ""
    if provider != "ollama":
        while True:
            hint = "（必填，无默认项）" if not current_key else "（默认：保持不变）"
            api_key = input(f"API Key{hint}: ").strip()
            if api_key:
                break
            if current_key:
                break
            print("[ERROR] 该 provider 需要 API Key，不能为空。")

    effective_key = api_key if api_key else current_key
    auto_models = profile["models"]
    if provider != "ollama":
        discovered = discover_models_openai_compatible(provider, current_base, effective_key)
        if discovered:
            auto_models = discovered
            print(f"[AUTO] 已探测到 {len(discovered)} 个模型。")
        else:
            print("[AUTO] 未探测到模型列表，使用内置默认模型。")

        quick = input("仅使用自动配置并保存? (Y/n): ").strip().lower()
        if quick in {"", "y", "yes"}:
            get_provider_store().upsert_profile(
                provider,
                api_base=current_base,
                api_key=effective_key or None,
                models=auto_models,
                enabled=True,
            )
            print(f"[OK] 已保存 {provider} 配置（自动模式）")
            return

    api_base_input = input(f"API Base [{current_base}]: ").strip()
    api_base = api_base_input or current_base

    # Common mistake: user pastes API key into API Base field.
    if looks_like_api_key(api_base_input) and not api_key and provider != "ollama":
        api_key = api_base_input
        effective_key = api_key
        api_base = current_base
        print("[WARN] 检测到你把 API Key 填到了 API Base，已自动纠正。")

    models_input = input(f"模型列表(逗号分隔) [{current_models}]: ").strip()
    enabled_input = input(f"启用? (y/n) [{'y' if profile['enabled'] else 'n'}]: ").strip().lower()
    enabled = profile["enabled"] if enabled_input == "" else enabled_input in {"y", "yes", "1"}
    models = (
        [m.strip() for m in models_input.split(",") if m.strip()]
        if models_input
        else auto_models
    )
    get_provider_store().upsert_profile(
        provider,
        api_base=api_base,
        api_key=effective_key if effective_key else None,
        models=models,
        enabled=enabled,
    )
    print(f"[OK] 已保存 {provider} 配置")


def print_help() -> None:
    print(
        "Commands: "
        "/help /clear /model <name> /providers /provider [/provider <id>] /provider-config [id] /quit"
    )
    print("Tools: write_file（新建与覆盖）/ delete_file 执行前均需在终端输入 y/yes 确认。")
    print(
        "Tips: /provider 切换厂商（已有 Key 则不再弹配置）；"
        "/provider-config 修改 Key 或 API Base；/help 查看全部命令。"
    )


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

        # Execute each tool call — only OpenAI-compatible keys (DeepSeek 等会校验 tool_calls[].type)
        assistant_msg = {
            "role": msg["role"],
            "content": msg.get("content"),
            "tool_calls": msg["tool_calls"],
        }
        messages.append(assistant_msg)

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
                tid_done = tc.get("id")
                if not tid_done:
                    raise RuntimeError("模型返回的 tool_call 缺少 id，无法对接 DeepSeek/OpenAI 兼容 API")
                messages.append({"role": "tool", "tool_call_id": tid_done, "content": summary})
                return summary

            # Execute and feed back
            result = execute_tool(name, args)
            print(f"  \033[2m{result[:500]}\033[0m")

            tool_msg: dict = {"role": "tool", "content": result}
            tid = tc.get("id")
            if not tid:
                raise RuntimeError("模型返回的 tool_call 缺少 id，无法对接 DeepSeek/OpenAI 兼容 API")
            tool_msg["tool_call_id"] = tid
            messages.append(tool_msg)

    print("\n\033[31m[max iterations reached]\033[0m")
    return "(max iterations)"


# ── Main REPL ───────────────────────────────────────────────────────


def runtime_environment_summary() -> str:
    """Truthful host description for system prompt (avoid claiming wrong OS)."""
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    return f"{system} {release} ({machine}), local CLI"


SYSTEM_PROMPT_TEMPLATE = """You are OpenAgentic, running as a local CLI assistant on the user's machine.

Runtime identity (MUST be truthful):
- host: {runtime_env}
- provider: {provider}
- model: {model}
- endpoint: {endpoint}

Capabilities:
- Optional tools can run shell commands on this host (OS-specific) and read files when the task requires it.
- `write_file` (新建或覆盖) / `delete_file` 都会在终端内要求用户输入 y/yes 确认；用户拒绝后只用文字说明，禁止用 `run_command` 重定向等方式绕过确认。
- On Windows, `run_command` uses cmd.exe by default: use `cd`, `dir`, `echo %CD%` instead of `pwd` / `ls -la` (those are Unix shells).
- For greetings, small talk, or general Q&A that does not need tools, reply normally in natural language — do not claim you are on a remote Linux server unless host above is actually Linux.

Rules:
1. Think step by step about what needs to be done.
2. Use tools only when they help accomplish the user's task.
3. After completing a task that used tools, call the `done` tool with a summary.
4. If the user asks a simple question that doesn't need tools, answer directly without calling any tool.
5. Never modify credentials or app config by surprise: prefer `/provider-config` instructions in text unless the user explicitly asked you to edit a specific file.
6. Keep command outputs concise; use OS-appropriate filtering (e.g. head/tail/grep on Unix).
7. If user asks what model/provider you are using, answer strictly from runtime identity above.
8. Never claim a different vendor/model (e.g., Claude/OpenAI/DeepSeek) unless it matches runtime identity."""


def build_system_prompt(provider: str, model: str, endpoint: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        runtime_env=runtime_environment_summary(),
        provider=provider,
        model=model,
        endpoint=endpoint,
    )


async def main_loop(model: str, provider: str, system_prompt: str | None = None):
    requested_provider = provider
    provider = resolve_provider(provider, model)
    model = resolve_model_for_provider(provider, model)

    # In auto mode: if default provider already has API Key, go straight to chat.
    if requested_provider == "auto":
        profile = find_profile(provider)
        if profile and provider != "ollama" and not profile["api_key"]:
            print("\n[配置向导] 当前默认厂商未配置 API Key。请先选择厂商，再按提示填写 Key。")
            selected = select_provider_interactive(provider)
            if selected:
                normalized = normalize_provider(selected)
                if find_profile(normalized):
                    provider = normalized
                    model = resolve_model_for_provider(provider, model)
                else:
                    print(f"[WARN] 未识别 provider: {selected}，继续使用 {provider}")

    api_base, api_key = require_provider_configured(provider)
    messages: list[dict] = []
    endpoint = api_base or "(provider default)"
    default_prompt = build_system_prompt(provider, model, endpoint)
    sp = system_prompt or default_prompt
    messages.append({"role": "system", "content": sp})

    print(f"\033[1mOpenAgentic Agent\033[0m  |  provider: {provider}  |  model: {model}")
    print("Tools: run_command, read_file, write_file（新建/覆盖均需确认）, delete_file（需确认）")
    print_help()
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
        if user_input == "/help":
            print_help()
            continue
        if user_input.startswith("/model "):
            model = resolve_model_for_provider(provider, user_input[7:].strip())
            print(f"[model → {model}]")
            continue
        if user_input == "/providers":
            print_provider_menu(provider)
            continue
        if user_input == "/provider":
            selected = select_provider_interactive(provider)
            if not selected:
                print("[provider unchanged]")
                continue
            provider = selected
            api_base, api_key = require_provider_configured(provider)
            model = resolve_model_for_provider(provider, model)
            endpoint = api_base or "(provider default)"
            messages[0] = {
                "role": "system",
                "content": build_system_prompt(provider, model, endpoint),
            }
            print(f"[provider → {provider}] [model → {model}]")
            continue
        if user_input.startswith("/provider "):
            selected = normalize_provider(user_input[10:].strip())
            if not find_profile(selected):
                print(f"[ERROR] 未知 provider: {selected}")
                continue
            provider = selected
            api_base, api_key = require_provider_configured(provider)
            model = resolve_model_for_provider(provider, model)
            endpoint = api_base or "(provider default)"
            messages[0] = {
                "role": "system",
                "content": build_system_prompt(provider, model, endpoint),
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
    maybe_auto_install_editable()
    parser = argparse.ArgumentParser(description="OpenAgentic Agent CLI (ReAct)")
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL}; OpenAI mode uses OPENAI_CHAT_MODEL when unchanged)",
    )
    parser.add_argument(
        "--provider",
        default="auto",
        help=(
            "LLM provider id "
            "(auto/openai/anthropic/xai/gemini/deepseek/mistral/cohere/groq/openrouter/"
            "moonshot/zhipu/minimax/volcengine/baidu/tencent/nvidia/together/fireworks/qwen/ollama)"
        ),
    )
    parser.add_argument("-s", "--system", default=None, help="Custom system prompt")
    args = parser.parse_args()
    asyncio.run(main_loop(args.model, args.provider, args.system))


if __name__ == "__main__":
    main()
