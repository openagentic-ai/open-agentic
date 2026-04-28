"""OpenAgentic CLI REPL — concurrent input queue (Producer-Consumer).

This file is intentionally narrow: bootstrap the session, run the
producer/consumer loop, dispatch slash commands. All handler bodies and UI
primitives live in :mod:`openagentic.cli.slash_commands`.
"""

from __future__ import annotations

import asyncio
import structlog
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from openagentic.cli._patchable_stdout import _patchable_stdout
from openagentic.cli.auth import clear_cli_session_file
from openagentic.cli.model_router import automodel_status, setup_automodel_interactive
from openagentic.cli.prompt import (
    build_core_memory_section,
    build_skills_section,
    compose_cli_system_message,
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
from openagentic.cli.slash_commands import (
    SlashCompleter,
    _SENTINEL_QUIT,
    _apply_automodel_defaults,
    _handle_btw,
    _handle_clear,
    _handle_compact,
    _handle_context,
    _handle_cost,
    _handle_diff,
    _handle_login_platform,
    _handle_permissions,
    _handle_review,
    _handle_skills_cmd,
    _make_prompt_msg,
    _make_toolbar,
    _run_react_turn,
    print_help,
)

logger = structlog.get_logger(__name__)
_console = Console(file=_patchable_stdout)


# ---------------------------------------------------------------------------
# main_loop — Producer-Consumer concurrent input queue
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
    session = PromptSession(completer=SlashCompleter())
    queue: asyncio.Queue = asyncio.Queue()

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
    model = _apply_automodel_defaults(provider, model)

    endpoint = api_base or "(provider default)"

    plat: dict[str, str | None] = {
        "base": platform_api_base,
        "email": platform_user_email,
        "token": platform_access_token,
    }
    messages: list[dict] = [{"role": "system", "content": ""}]

    # 首次启动播种内置 skill 到 ~/.openagentic/skills/（不覆盖用户已有同名）
    try:
        from openagentic.skills import SkillsManager
        seeded = SkillsManager().ensure_seeded()
        if seeded:
            _console.print(
                f"  [dim]seeded {len(seeded)} builtin skill(s): {', '.join(seeded)}[/dim]"
            )
    except Exception as exc:  # 播种失败不该阻断 CLI 启动
        logger.warning("skills seeding failed", error=str(exc), exc_info=True)

    def rebuild_system_message() -> None:
        base = compose_cli_system_message(
            provider,
            model,
            endpoint,
            system_prompt_override=system_prompt,
            platform_api_base=plat["base"],
            platform_user_email=plat["email"],
        )
        core = build_core_memory_section(limit=20)
        if core:
            base += "\n" + core
        skills_section = build_skills_section()
        if skills_section:
            base += "\n" + skills_section
        messages[0]["content"] = base

    rebuild_system_message()

    # ── async confirm callback for tools ──
    # During confirmation, pause the input producer so prompts don't collide.
    input_gate = asyncio.Event()
    input_gate.set()  # start open

    # ── 进行中的 react 任务引用：用于 Ctrl+C 中断当前轮而不退 CLI ──
    react_task_ref: dict[str, asyncio.Task | None] = {"task": None}

    async def _confirm_fn(title: str, detail: str) -> bool:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False
        input_gate.clear()  # pause producer
        try:
            _console.print()
            _console.print(f"[yellow bold]? {title}[/yellow bold]")
            _console.print(f"  [dim]{detail}[/dim]")
            ans = await session.prompt_async("  Confirm? (Y/N): ")
            return (ans or "").strip().lower() in ("y", "yes")
        finally:
            input_gate.set()  # resume producer

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
    _console.print("  [dim]Type /help for commands.[/dim]")
    _console.print()

    # ── Input Producer: always accepts input, puts into queue ──
    # patch_stdout() wraps the entire producer lifecycle so that ALL
    # output from the consumer (react_loop, Rich prints, etc.) is
    # redirected above the prompt. The prompt stays fixed at the
    # bottom of the terminal at all times.
    async def _input_producer():
        with patch_stdout():
            while True:
                await input_gate.wait()  # pause during tool confirmation
                try:
                    user_input = await session.prompt_async(
                        _make_prompt_msg(),
                        bottom_toolbar=_make_toolbar(queue.qsize()),
                    )
                except EOFError:
                    await queue.put(_SENTINEL_QUIT)
                    return
                except KeyboardInterrupt:
                    # 若当前有进行中的 react 任务：取消它，回到 prompt，CLI 不退
                    in_flight = react_task_ref["task"]
                    if in_flight is not None and not in_flight.done():
                        in_flight.cancel()
                        # consumer 那边 await 会拿到 CancelledError，自己打印 "Cancelled."
                        continue
                    # 空闲态 Ctrl+C 仍然退出（保留原行为，符合用户对终端的直觉）
                    await queue.put(_SENTINEL_QUIT)
                    return

                user_input = (user_input or "").strip()
                if not user_input:
                    continue
                await queue.put(user_input)

    # ── Execution Consumer: processes queued commands sequentially ──
    async def _execution_consumer():  # noqa: C901
        nonlocal model, provider, api_base, api_key, endpoint, automodel_enabled

        while True:
            item = await queue.get()

            if item is _SENTINEL_QUIT:
                return

            user_input: str = item

            # ── Slash commands ──
            if user_input == "/quit":
                return
            if user_input == "/clear":
                _handle_clear(messages, rebuild_system_message)
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
                # Interactive model selection — pause producer
                input_gate.clear()
                try:
                    choice = (await session.prompt_async("  Select: ")).strip()
                except (EOFError, KeyboardInterrupt):
                    input_gate.set()
                    continue
                input_gate.set()
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
                _console.print(f"  [green]model -> {model}[/green] [dim]({provider})[/dim]")
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
                _console.print(f"  [green]model -> {model}[/green] [dim](automodel stays on)[/dim]")
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
                await _handle_login_platform(plat, session, input_gate, rebuild_system_message)
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
                elif arg == "setup":
                    if setup_automodel_interactive(provider):
                        automodel_enabled = True
                        _console.print("  [green]automodel ON[/green]")
                    continue
                else:
                    _console.print("  [red]Usage: /automodel on|off|setup[/red]")
                    continue

            if user_input == "/skills" or user_input.startswith("/skills "):
                _handle_skills_cmd(
                    user_input[len("/skills"):].strip(), rebuild_system_message,
                )
                continue

            if user_input == "/compact":
                await _handle_compact(messages, model, api_base, api_key)
                continue
            if user_input == "/context":
                _handle_context(messages)
                continue
            if user_input == "/cost":
                _handle_cost()
                continue
            if user_input == "/permissions" or user_input.startswith("/permissions "):
                _handle_permissions(user_input[len("/permissions"):])
                continue
            if user_input.startswith("/btw"):
                note = user_input[len("/btw"):].strip()
                if not note:
                    _console.print("  [red]Usage: /btw <text>[/red]")
                    continue
                _handle_btw(messages, note)
                continue

            if user_input == "/diff" or user_input.startswith("/diff "):
                _handle_diff(user_input[len("/diff"):])
                continue

            if user_input == "/review" or user_input.startswith("/review "):
                await _handle_review(user_input[len("/review"):], queue)
                continue

            if user_input == "/config":
                _console.print()
                _console.print(f"  [bold]provider:[/bold] {provider}")
                _console.print(f"  [bold]model:[/bold]    {model}")
                _console.print(f"  [bold]endpoint:[/bold] {endpoint}")
                _console.print(f"  [bold]automodel:[/bold] {'on' if automodel_enabled else 'off'}")
                if plat["email"]:
                    _console.print(f"  [bold]platform:[/bold] {plat['email']}")
                _console.print()
                continue

            # ── 用户对话轮次：triage 路由 → react_loop（可取消）→ 复位路由后的模型 ──
            model = await _run_react_turn(
                user_input,
                messages,
                provider=provider,
                model=model,
                api_base=api_base,
                api_key=api_key,
                automodel_enabled=automodel_enabled,
                plat=plat,
                confirm_fn=_confirm_fn,
                react_task_ref=react_task_ref,
                rebuild_system_message=rebuild_system_message,
            )

            _console.print()
            sys.stdout.flush()

    # ── Launch both tasks concurrently ──
    producer = asyncio.create_task(_input_producer())
    consumer = asyncio.create_task(_execution_consumer())

    # Wait for either to finish (quit signal or error)
    done, pending = await asyncio.wait(
        [producer, consumer],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel the other task
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Clear the stray "❯ " prompt_toolkit already rendered before the
    # producer was cancelled — otherwise it sits right before Bye!.
    sys.stdout.write("\x1b[2K\r")
    sys.stdout.flush()
    _console.print("[dim]Bye![/dim]")
