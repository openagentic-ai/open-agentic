"""OpenAgentic CLI REPL — sequential prompt → process loop."""

from __future__ import annotations

import asyncio
import shutil
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from openagentic.cli.auth import clear_cli_session_file, platform_authenticate_sync
from openagentic.cli.model_router import automodel_status, route_model
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

_console = Console()


def print_help() -> None:
    _console.print()
    _console.print("[bold]Commands[/bold]")
    _console.print(
        "  /help  /config  /clear  /model <name>  /providers  /provider [id]  "
        "/provider-config [id]"
    )
    _console.print(
        "  /automodel [on|off]  /login-platform  /logout-platform  /quit"
    )
    _console.print()
    _console.print("[bold]Tips[/bold]")
    _console.print("  write_file / delete_file need Y/N confirmation before execution")
    _console.print()


# ---------------------------------------------------------------------------
# main_loop — sequential prompt → process → prompt ...
# ---------------------------------------------------------------------------

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
):  # noqa: C901
    session = PromptSession()

    requested_provider = provider
    provider = resolve_provider(provider, model)
    model = resolve_model_for_provider(provider, model)

    if requested_provider == "auto":
        profile = find_profile(provider)
        if profile and provider != "ollama" and not profile["api_key"]:
            _console.print("\n[yellow]No API key configured. Please select a provider.[/yellow]")
            selected = select_provider_interactive(provider)
            if selected:
                normalized = normalize_provider(selected)
                if find_profile(normalized):
                    provider = normalized
                    model = resolve_model_for_provider(provider, model)
                else:
                    _console.print(f"[yellow]Unknown provider: {selected}, using {provider}[/yellow]")

    api_base, api_key = require_provider_configured(provider)

    if env_base_url:
        api_base = env_base_url
    if env_auth_token:
        api_key = env_auth_token

    automodel_enabled = True
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

    # ── async confirm callback for tools ──
    async def _confirm_fn(title: str, detail: str) -> bool:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False
        _console.print()
        _console.print(f"[yellow bold]? {title}[/yellow bold]")
        _console.print(f"  [dim]{detail}[/dim]")
        with patch_stdout():
            ans = await session.prompt_async("  Confirm? (Y/N): ")
        return (ans or "").strip().lower() in ("y", "yes")

    # ── Welcome banner ──
    _console.print()
    _console.rule("[bold]OpenAgentic Agent[/bold]", style="dim")
    info_parts = [f"[bold]{provider}[/bold]", f"[cyan]{model}[/cyan]"]
    if env_base_url or env_auth_token:
        info_parts.append("[dim](env override)[/dim]")
    _console.print(f"  {' / '.join(info_parts)}")
    if env_base_url:
        _console.print(f"  [dim]endpoint: {env_base_url}[/dim]")
    if plat["email"] and plat["base"]:
        _console.print(f"  [dim]{plat['email']} @ {plat['base'].rstrip('/')}[/dim]")
    _console.print(f"  [dim]Type /help for commands.[/dim]")
    _console.print()

    # ── Sequential main loop: prompt → process → prompt → ... ──
    while True:
        # Show prompt and wait for input (no raw mode during execution)
        try:
            with patch_stdout():
                HINT = "  /help  |  /config  |  /model  |  /quit"

                def _get_toolbar():
                    w = shutil.get_terminal_size().columns
                    bar = '─' * max(0, w - 2)
                    return HTML(
                        f'<style fg="#666666">╰{bar}╯</style>\n'
                        f'<style fg="#555555">  {HINT}</style>'
                    )

                w = shutil.get_terminal_size().columns
                top_bar = '─' * max(0, w - 2)
                user_input = await session.prompt_async(
                    HTML(
                        f'<style fg="#666666">╭{top_bar}╮</style>\n'
                        '<b>&gt;</b> '
                    ),
                    bottom_toolbar=_get_toolbar,
                )
        except EOFError:
            break
        except KeyboardInterrupt:
            break

        user_input = (user_input or "").strip()
        if not user_input:
            continue

        # ── Slash commands ──
        if user_input == "/quit":
            _console.print("[dim]Bye![/dim]")
            break
        if user_input == "/clear":
            messages.clear()
            messages.append({"role": "system", "content": ""})
            rebuild_system_message()
            _console.print("[green]  history cleared[/green]")
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
                _console.print("[yellow]  No models available.[/yellow]")
                continue
            _console.print(f"\n  [bold]Current:[/bold] {model} [dim]({provider})[/dim]\n")
            for idx, m in enumerate(all_models, 1):
                marker = " [green]<-[/green]" if m == model else ""
                _console.print(f"  {idx}. {m}{marker}")
            _console.print()
            try:
                with patch_stdout():
                    choice = (await session.prompt_async("  Select: ")).strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if not choice:
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(all_models):
                selected_model = all_models[int(choice) - 1]
            else:
                selected_model = resolve_model_for_provider(provider, choice)
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
            automodel_enabled = False
            _console.print(f"  [green]model -> {model}[/green] [dim]({provider}, automodel off)[/dim]")
            rebuild_system_message()
            continue
        if user_input.startswith("/model "):
            candidate = resolve_model_for_provider(provider, user_input[7:].strip())
            profile = find_profile(provider)
            available = profile["models"] if profile else []
            if available and candidate not in available:
                _console.print(f"  [red]Model '{candidate}' not in {provider}[/red]")
                _console.print(f"  [dim]Available: {', '.join(available)}[/dim]")
                continue
            model = candidate
            automodel_enabled = False
            _console.print(f"  [green]model -> {model}[/green] [dim](automodel off)[/dim]")
            rebuild_system_message()
            continue
        if user_input == "/providers":
            print_provider_menu(provider)
            continue
        if user_input == "/provider":
            selected = select_provider_interactive(provider)
            if not selected:
                continue
            provider = selected
            api_base, api_key = require_provider_configured(provider)
            model = resolve_model_for_provider(provider, model)
            endpoint = api_base or "(provider default)"
            automodel_enabled = False
            rebuild_system_message()
            _console.print(f"  [green]provider -> {provider}[/green] [dim](model: {model})[/dim]")
            continue
        if user_input.startswith("/provider "):
            selected = normalize_provider(user_input[10:].strip())
            if not find_profile(selected):
                _console.print(f"  [red]Unknown provider: {selected}[/red]")
                continue
            provider = selected
            api_base, api_key = require_provider_configured(provider)
            model = resolve_model_for_provider(provider, model)
            endpoint = api_base or "(provider default)"
            automodel_enabled = False
            rebuild_system_message()
            _console.print(f"  [green]provider -> {provider}[/green] [dim](model: {model})[/dim]")
            continue
        if user_input == "/logout-platform":
            clear_cli_session_file()
            plat["token"] = None
            plat["email"] = None
            rebuild_system_message()
            _console.print("  [green]Logged out.[/green] [dim]Use /login-platform to re-login.[/dim]")
            continue
        if user_input == "/login-platform":
            base = (plat["base"] or "").strip()
            if not base:
                try:
                    with patch_stdout():
                        base = (await session.prompt_async(
                            "  Server URL (e.g. http://127.0.0.1:8000): "
                        )).strip()
                except (EOFError, KeyboardInterrupt):
                    continue
            if not base:
                _console.print("  [red]URL required.[/red]")
                continue
            plat["base"] = base.rstrip("/")
            tok, em = platform_authenticate_sync(plat["base"])
            plat["token"] = tok
            plat["email"] = em
            rebuild_system_message()
            _console.print(f"  [green]Logged in:[/green] {em}")
            continue
        if user_input.startswith("/provider-config"):
            target = user_input.replace("/provider-config", "", 1).strip() or provider
            configure_provider_interactive(target)
            if target == provider:
                api_base, api_key = require_provider_configured(provider)
                endpoint = api_base or "(provider default)"
                rebuild_system_message()
            continue

        # ── /automodel ──
        if user_input == "/automodel":
            _console.print(f"  {automodel_status(provider, automodel_enabled)}")
            continue
        if user_input.startswith("/automodel "):
            arg = user_input[11:].strip().lower()
            if arg in ("on", "enable", "1", "true", "yes"):
                automodel_enabled = True
                _console.print("  [green]automodel ON[/green]")
                continue
            elif arg in ("off", "disable", "0", "false", "no"):
                automodel_enabled = False
                _console.print(f"  [green]automodel OFF[/green] [dim](locked: {model})[/dim]")
                continue
            else:
                _console.print("  [red]Usage: /automodel on|off[/red]")
                continue

        if user_input == "/config":
            _console.print(f"\n{build_identity_answer(provider, model, endpoint)}")
            continue

        if is_identity_question(user_input):
            identity_answer = build_identity_answer(provider, model, endpoint)
            _console.print(f"\n{identity_answer}")
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": identity_answer})
            continue

        # ── DeepSeek Pro/Flash auto-routing ──
        current_model = model
        routed_model, hint = route_model(
            user_input,
            provider,
            current_model,
            automodel_enabled=automodel_enabled,
        )
        if hint:
            _console.print(f"  [dim]{hint}[/dim]")
        if routed_model != current_model:
            model = routed_model
            rebuild_system_message()

        # ── Execute react loop ──
        try:
            await react_loop(
                user_input,
                messages,
                model,
                api_base,
                api_key,
                platform_api_base=plat["base"],
                platform_user_email=plat["email"],
                confirm_fn=_confirm_fn,
            )
        except Exception as e:
            _console.print(f"\n  [red bold]Error:[/red bold] {type(e).__name__}: {e}")
        _console.print()  # blank line after response
        sys.stdout.flush()  # ensure clean state before next prompt

    _console.print("\n[dim]Bye![/dim]")
