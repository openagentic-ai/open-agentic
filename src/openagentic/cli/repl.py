"""模块说明（中文）：`src/openagentic/cli/repl.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

from __future__ import annotations

import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout

from openagentic.cli.auth import clear_cli_session_file, platform_authenticate_sync
from openagentic.cli.platform_adapter import CLI_PLATFORM
from openagentic.cli.prompt import (
    build_identity_answer,
    compose_cli_system_message,
    is_identity_question,
)
from openagentic.cli.providers import (
    configure_provider_interactive,
    find_profile,
    normalize_provider,
    print_provider_menu,
    require_provider_configured,
    resolve_model_for_provider,
    resolve_provider,
    select_provider_interactive,
)
from openagentic.cli.react import react_loop


def print_help() -> None:
    print(
        "Commands: "
        "/help /clear /model <name> /providers /provider [/provider <id>] /provider-config [id] "
        "/login-platform /logout-platform /quit"
    )
    print("Tools: write_file（新建与覆盖）/ delete_file 执行前均需在终端输入 y/yes 确认。")
    print(
        "Tips: /provider 切换厂商（已有 Key 则不再弹配置）；"
        "/provider-config 修改 Key 或 API Base；/help 查看全部命令。"
    )
    print(
        "平台账号: 启动时 `--require-auth` / `--api-base URL` 会要求登录或注册（JWT）；"
        "会话内可用 /login-platform、/logout-platform。与 LLM 厂商 API Key 是两层认证。"
    )


async def main_loop(
    model: str,
    provider: str,
    system_prompt: str | None = None,
    *,
    platform_api_base: str | None = None,
    platform_user_email: str | None = None,
    platform_access_token: str | None = None,
    env_base_url: str | None = None,
    env_auth_token: str | None = None,
):
    session = PromptSession()

    def _term_width() -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    def _print_separator(style: str = "dim") -> None:
        w = _term_width()
        if style == "bold":
            print(f"\033[1m{'─' * w}\033[0m")
        else:
            print(f"\033[2m{'─' * w}\033[0m")

    async def _read_line(prompt_text: str) -> str:
        CLI_PLATFORM.ensure_line_input_mode()
        CLI_PLATFORM.drain_stdin_buffer(settle_ms=80)
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return input(prompt_text)
        try:
            with patch_stdout():
                return await session.prompt_async(prompt_text)
        except Exception:
            return input(prompt_text)

    requested_provider = provider
    provider = resolve_provider(provider, model)
    model = resolve_model_for_provider(provider, model)

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

    # OPENAGENTIC_* env-var overrides take priority
    if env_base_url:
        api_base = env_base_url
    if env_auth_token:
        api_key = env_auth_token
    endpoint = api_base or "(provider default)"

    plat: dict[str, str | None] = {
        "base": platform_api_base,
        "email": platform_user_email,
        "token": platform_access_token,
    }
    messages: list[dict] = [{"role": "system", "content": ""}]

    def rebuild_system_message() -> None:
        messages[0]["content"] = compose_cli_system_message(
            provider,
            model,
            endpoint,
            system_prompt_override=system_prompt,
            platform_api_base=plat["base"],
            platform_user_email=plat["email"],
        )

    rebuild_system_message()

    env_hint = " (via OPENAGENTIC_* env)" if env_base_url or env_auth_token else ""
    print()
    _print_separator("bold")
    print(f"  \033[1mOpenAgentic Agent\033[0m  \033[2m│\033[0m  {provider}  \033[2m│\033[0m  {model}{env_hint}")
    if env_base_url:
        print(f"  \033[2mendpoint: {env_base_url}\033[0m")
    if plat["email"] and plat["base"]:
        print(f"  \033[2mplatform: {plat['email']} @ {plat['base'].rstrip('/')}\033[0m")
    _print_separator("bold")
    print_help()

    while True:
        try:
            print()
            _print_separator()
            user_input = (await _read_line("\033[1m❯\033[0m ")).strip()
            _print_separator()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("Bye!")
            break
        if user_input == "/clear":
            messages.clear()
            messages.append({"role": "system", "content": ""})
            rebuild_system_message()
            print("\n  \033[2m✓ history cleared\033[0m")
            continue
        if user_input == "/help":
            print_help()
            continue
        if user_input == "/model":
            from openagentic.core.llm.provider_config import get_provider_store
            all_profiles = get_provider_store().get().profiles
            all_models = []
            for p in all_profiles:
                if p.enabled:
                    all_models.extend(p.models)
            if not all_models:
                print("[WARN] 没有可用模型。")
                continue
            print(f"\n当前模型: {model}")
            print(f"当前 provider: {provider}\n")
            print("可用模型:")
            for idx, m in enumerate(all_models, 1):
                marker = " ←" if m == model else ""
                print(f"  {idx}. {m}{marker}")
            print(f"\n输入序号或模型名切换，直接回车取消。")
            try:
                choice = (await _read_line("选择: ")).strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if not choice:
                print("[model unchanged]")
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(all_models):
                selected_model = all_models[int(choice) - 1]
            else:
                selected_model = resolve_model_for_provider(provider, choice)
            # 找到新模型对应的 provider
            new_provider = provider
            for p in all_profiles:
                if p.enabled and selected_model in p.models:
                    new_provider = p.id
                    break
            if new_provider != provider:
                provider = new_provider
                api_base, api_key = require_provider_configured(provider)
                endpoint = api_base or "(provider default)"
            model = selected_model
            print(f"[model → {model}] [provider → {provider}]")
            rebuild_system_message()
            continue
        if user_input.startswith("/model "):
            candidate = resolve_model_for_provider(provider, user_input[7:].strip())
            profile = find_profile(provider)
            available = profile["models"] if profile else []
            if available and candidate not in available:
                print(f"[ERROR] 模型 '{candidate}' 不在当前 provider ({provider}) 的可用列表中。")
                print(f"  可用模型: {', '.join(available)}")
                continue
            model = candidate
            print(f"[model → {model}]")
            rebuild_system_message()
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
            rebuild_system_message()
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
            rebuild_system_message()
            print(f"[provider → {provider}] [model → {model}]")
            continue
        if user_input == "/logout-platform":
            clear_cli_session_file()
            plat["token"] = None
            plat["email"] = None
            rebuild_system_message()
            print(
                "[平台] 已退出登录（本地 JWT 会话文件已删除）。"
                "若曾指定过服务地址，可直接 /login-platform；否则请先输入 URL。"
            )
            continue
        if user_input == "/login-platform":
            base = (plat["base"] or "").strip()
            if not base:
                base = (await _read_line("OpenAgentic 根 URL（如 http://127.0.0.1:8000，回车取消）: ")).strip()
            if not base:
                print("[ERROR] 需要有效的服务地址")
                continue
            plat["base"] = base.rstrip("/")
            tok, em = platform_authenticate_sync(plat["base"])
            plat["token"] = tok
            plat["email"] = em
            rebuild_system_message()
            print(f"[平台] 已登录: {em}")
            continue
        if user_input.startswith("/provider-config"):
            target = user_input.replace("/provider-config", "", 1).strip() or provider
            configure_provider_interactive(target)
            if target == provider:
                api_base, api_key = require_provider_configured(provider)
                endpoint = api_base or "(provider default)"
                rebuild_system_message()
            continue
        if is_identity_question(user_input):
            identity_answer = build_identity_answer(provider, model, endpoint)
            print(f"\n{identity_answer}")
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": identity_answer})
            continue

        try:
            await react_loop(
                user_input,
                messages,
                model,
                api_base,
                api_key,
                platform_api_base=plat["base"],
                platform_user_email=plat["email"],
            )
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
