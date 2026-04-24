"""模块说明（中文）：`src/openagentic/cli/prompt.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import platform
import re

IDENTITY_QUESTION_RE = re.compile(
    r"(你背后|你用的|什么模型|哪个模型|provider|底层模型|大模型|what model|which model|model provider)",
    re.IGNORECASE,
)


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

CLI slash commands (handled by the CLI shell, NOT by you — just tell the user to type them):
- `/model <name>` — switch to a different model (e.g. `/model deepseek-reasoner`)
- `/provider` — interactive provider selection menu
- `/provider <id>` — switch provider directly (e.g. `/provider openai`)
- `/provider-config [id]` — configure API key / base URL for a provider
- `/providers` — list all available providers
- `/clear` — clear conversation history
- `/help` — show all commands
- `/quit` — exit
When the user asks to change model, switch provider, etc., tell them the exact slash command to type. Do NOT say you cannot do it.

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


def compose_cli_system_message(
    provider: str,
    model: str,
    endpoint: str,
    *,
    system_prompt_override: str | None,
    platform_api_base: str | None,
    platform_user_email: str | None,
) -> str:
    sp = system_prompt_override or build_system_prompt(provider, model, endpoint)
    if platform_user_email and platform_api_base:
        sp += (
            f"\n\nOpenAgentic 平台账号（已通过该服务的 JWT 认证）: {platform_user_email} "
            f"(API {platform_api_base.rstrip('/')})"
        )
    return sp


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
