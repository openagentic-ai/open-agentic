"""CLI read-eval-print loop (commands + chat turns)."""

from __future__ import annotations

from openagentic.cli.auth import clear_cli_session_file, platform_authenticate_sync
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
    print("Tools: write_file锛堟柊寤轰笌瑕嗙洊锛? delete_file 鎵ц鍓嶅潎闇€鍦ㄧ粓绔緭鍏?y/yes 纭銆?)
    print(
        "Tips: /provider 鍒囨崲鍘傚晢锛堝凡鏈?Key 鍒欎笉鍐嶅脊閰嶇疆锛夛紱"
        "/provider-config 淇敼 Key 鎴?API Base锛?help 鏌ョ湅鍏ㄩ儴鍛戒护銆?
    )
    print(
        "骞冲彴璐﹀彿: 鍚姩鏃?`--require-auth` / `--api-base URL` 浼氳姹傜櫥褰曟垨娉ㄥ唽锛圝WT锛夛紱"
        "浼氳瘽鍐呭彲鐢?/login-platform銆?logout-platform銆備笌 LLM 鍘傚晢 API Key 鏄袱灞傝璇併€?
    )


async def main_loop(
    model: str,
    provider: str,
    system_prompt: str | None = None,
    *,
    platform_api_base: str | None = None,
    platform_user_email: str | None = None,
    platform_access_token: str | None = None,
):
    requested_provider = provider
    provider = resolve_provider(provider, model)
    model = resolve_model_for_provider(provider, model)

    if requested_provider == "auto":
        profile = find_profile(provider)
        if profile and provider != "ollama" and not profile["api_key"]:
            print("\n[閰嶇疆鍚戝] 褰撳墠榛樿鍘傚晢鏈厤缃?API Key銆傝鍏堥€夋嫨鍘傚晢锛屽啀鎸夋彁绀哄～鍐?Key銆?)
            selected = select_provider_interactive(provider)
            if selected:
                normalized = normalize_provider(selected)
                if find_profile(normalized):
                    provider = normalized
                    model = resolve_model_for_provider(provider, model)
                else:
                    print(f"[WARN] 鏈瘑鍒?provider: {selected}锛岀户缁娇鐢?{provider}")

    api_base, api_key = require_provider_configured(provider)
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

    print(f"\033[1mOpenAgentic Agent\033[0m  |  provider: {provider}  |  model: {model}")
    if plat["email"] and plat["base"]:
        print(f"  platform: {plat['email']} @ {plat['base'].rstrip('/')}")
    print("Tools: run_command, read_file, write_file锛堟柊寤?瑕嗙洊鍧囬渶纭锛? delete_file锛堥渶纭锛?)
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
            messages.clear()
            messages.append({"role": "system", "content": ""})
            rebuild_system_message()
            print("[history cleared]")
            continue
        if user_input == "/help":
            print_help()
            continue
        if user_input.startswith("/model "):
            model = resolve_model_for_provider(provider, user_input[7:].strip())
            print(f"[model 鈫?{model}]")
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
            print(f"[provider 鈫?{provider}] [model 鈫?{model}]")
            continue
        if user_input.startswith("/provider "):
            selected = normalize_provider(user_input[10:].strip())
            if not find_profile(selected):
                print(f"[ERROR] 鏈煡 provider: {selected}")
                continue
            provider = selected
            api_base, api_key = require_provider_configured(provider)
            model = resolve_model_for_provider(provider, model)
            endpoint = api_base or "(provider default)"
            rebuild_system_message()
            print(f"[provider 鈫?{provider}] [model 鈫?{model}]")
            continue
        if user_input == "/logout-platform":
            clear_cli_session_file()
            plat["token"] = None
            plat["email"] = None
            rebuild_system_message()
            print(
                "[骞冲彴] 宸查€€鍑虹櫥褰曪紙鏈湴 JWT 浼氳瘽鏂囦欢宸插垹闄わ級銆?
                "鑻ユ浘鎸囧畾杩囨湇鍔″湴鍧€锛屽彲鐩存帴 /login-platform锛涘惁鍒欒鍏堣緭鍏?URL銆?
            )
            continue
        if user_input == "/login-platform":
            base = (plat["base"] or "").strip() or input(
                "OpenAgentic 鏍?URL锛堝 http://127.0.0.1:8000锛屽洖杞﹀彇娑堬級: "
            ).strip()
            if not base:
                print("[ERROR] 闇€瑕佹湁鏁堢殑鏈嶅姟鍦板潃")
                continue
            plat["base"] = base.rstrip("/")
            tok, em = platform_authenticate_sync(plat["base"])
            plat["token"] = tok
            plat["email"] = em
            rebuild_system_message()
            print(f"[骞冲彴] 宸茬櫥褰? {em}")
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
            print(f"\n\033[32m{identity_answer}\033[0m")
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
            print(f"\033[31m[ERROR] {type(e).__name__}: {e}\033[0m")
