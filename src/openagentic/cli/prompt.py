"""模块说明（中文）：`src/openagentic/cli/prompt.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import platform
import re

# Only trigger on explicit slash-command or very specific standalone questions.
# DO NOT match general conversation that merely mentions "模型" / "大模型".
IDENTITY_QUESTION_RE = re.compile(
    r"^(你是什么模型|你用的什么模型|当前是什么模型|当前用的什么模型)$",
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
- `/model <name>` — switch to a different model (e.g. `/model deepseek-v4-pro`)
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


def build_core_memory_section(limit: int = 20) -> str:
    """Load top core memory entries from file storage and format them
    for injection into the system prompt."""
    try:
        from openagentic.memory.manager import MemoryManager
        mgr = MemoryManager()
        entries = mgr.list_core(limit=limit)
    except Exception:
        return ""

    if not entries:
        return ""

    lines = [
        "",
        "## Persistent Core Memory",
        "The following was saved from previous interactions. Use these facts to personalize responses.",
        "",
    ]
    for e in entries:
        cat = e.category.replace("_", " ").title()
        lines.append(f"- [{cat}] {e.key}: {e.value}")
    return "\n".join(lines)


def build_skills_section() -> str:
    """List discovered skills as one-line metadata for the LLM.

    只塞 name+description+path（每个 skill ~50 token），全文按需 read_file。
    跳过解析失败的 skill（loader 已记录错误，但不污染 prompt）。
    """
    try:
        from openagentic.skills import SkillsManager
        skills = SkillsManager().list_skills()
    except Exception:
        return ""

    if not skills:
        return ""

    lines = [
        "",
        "## Available Skills",
        "你可以使用以下 skill。需要时用 `read_file` 读取其 SKILL.md 全文获取详细操作指南，",
        "然后按指南的步骤执行。skill 不是工具——它是给你的领域 SOP。",
        "",
    ]
    for s in skills:
        lines.append(f"- **{s.slug}** (`{s.path}`): {s.description}")
    lines.append("")
    lines.append("调用模式：判断当前任务匹配某 skill → read_file 该 SKILL.md → 按其指南执行。")
    return "\n".join(lines)


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
