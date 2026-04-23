"""CLI system prompt and identity helpers."""

from __future__ import annotations

import platform
import re

IDENTITY_QUESTION_RE = re.compile(
    r"(浣犺儗鍚巪浣犵敤鐨剕浠€涔堟ā鍨媩鍝釜妯″瀷|provider|搴曞眰妯″瀷|澶фā鍨媩what model|which model|model provider)",
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
- `write_file` (鏂板缓鎴栬鐩? / `delete_file` 閮戒細鍦ㄧ粓绔唴瑕佹眰鐢ㄦ埛杈撳叆 y/yes 纭锛涚敤鎴锋嫆缁濆悗鍙敤鏂囧瓧璇存槑锛岀姝㈢敤 `run_command` 閲嶅畾鍚戠瓑鏂瑰紡缁曡繃纭銆?
- On Windows, `run_command` uses cmd.exe by default: use `cd`, `dir`, `echo %CD%` instead of `pwd` / `ls -la` (those are Unix shells).
- For greetings, small talk, or general Q&A that does not need tools, reply normally in natural language 鈥?do not claim you are on a remote Linux server unless host above is actually Linux.

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
            f"\n\nOpenAgentic 骞冲彴璐﹀彿锛堝凡閫氳繃璇ユ湇鍔＄殑 JWT 璁よ瘉锛? {platform_user_email} "
            f"(API {platform_api_base.rstrip('/')})"
        )
    return sp


def is_identity_question(text: str) -> bool:
    return bool(IDENTITY_QUESTION_RE.search(text))


def build_identity_answer(provider: str, model: str, endpoint: str) -> str:
    return (
        "褰撳墠杩愯鏃堕厤缃涓嬶細\n"
        f"- host: {runtime_environment_summary()}\n"
        f"- provider: {provider}\n"
        f"- model: {model}\n"
        f"- endpoint: {endpoint}\n"
    )
