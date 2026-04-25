"""OpenAgentic CLI REPL — concurrent input queue (Producer-Consumer)."""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from openagentic.cli._patchable_stdout import _patchable_stdout
from openagentic.cli.auth import clear_cli_session_file, platform_authenticate_sync
from openagentic.cli.model_router import automodel_status, route_model, setup_automodel_interactive
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
from openagentic.cli.react import react_loop

logger = logging.getLogger(__name__)
_console = Console(file=_patchable_stdout)

SLASH_COMMANDS = [
    "/help", "/config", "/model", "/provider", "/providers",
    "/provider-config", "/automodel", "/clear",
    "/skills",
    "/login-platform", "/logout-platform", "/quit",
]

_SENTINEL_QUIT = object()


class SlashCompleter(Completer):
    """Auto-complete slash commands when input starts with '/'."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for cmd in SLASH_COMMANDS:
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text))


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
    _console.print(
        "  /skills [name]  /skills new <name>  /skills reload"
    )
    _console.print()
    _console.print("[bold]Tips[/bold]")
    _console.print("  write_file / delete_file need Y/N confirmation before execution")
    _console.print()


def _make_prompt_msg() -> HTML:
    w = shutil.get_terminal_size().columns
    inner = w - 2 if w >= 2 else w
    top_bar = '─' * inner
    return HTML(
        f'<style fg="#666666">╭{top_bar}╮</style>\n'
        f'<b>❯</b> '
    )


def _make_toolbar(pending: int = 0):
    def _get_toolbar():
        w = shutil.get_terminal_size().columns
        inner = w - 2 if w >= 2 else w
        bar = '─' * inner
        try:
            app = get_app()
            text = app.current_buffer.text
        except Exception:
            text = ""

        pending_hint = f"  [{pending} pending]" if pending > 0 else ""

        if text.startswith("/"):
            matching = [c for c in SLASH_COMMANDS if c.startswith(text)]
            if matching:
                hint = "  ".join(matching)
            else:
                hint = f"  未知命令：{text}"
            return HTML(
                f'<style fg="#666666">╰{bar}╯</style>\n'
                f'<style fg="#aaaaaa">  {hint}{pending_hint}</style>'
            )
        return HTML(
            f'<style fg="#666666">╰{bar}╯</style>\n'
            f'<style fg="#555555">  /help · 按 / 查看命令{pending_hint}</style>'
        )
    return _get_toolbar


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

    # ── Auto-detect / apply automodel config ──
    from openagentic.cli.model_router import _get_automodel_config
    am_cfg = _get_automodel_config(provider)
    if am_cfg and am_cfg.get("simple_model"):
        model = am_cfg["simple_model"]
    else:
        # Try to auto-detect cheap/expensive model pairs by naming convention
        profile = find_profile(provider)
        models_list = profile["models"] if profile else []
        if len(models_list) >= 2:
            cheap_kw = ["flash", "mini", "lite", "nano", "tiny", "small", "fast"]
            exp_kw = ["pro", "max", "ultra", "large", "premium", "op"]
            cheap = next((m for m in models_list if any(k in m.lower() for k in cheap_kw)), None)
            expensive = next((m for m in models_list if any(k in m.lower() for k in exp_kw)), None)
            # If only one direction found, infer the other from the remaining models
            if cheap and not expensive:
                others = [m for m in models_list if m != cheap]
                if others:
                    expensive = others[0]  # pick first non-cheap as complex
            elif expensive and not cheap:
                others = [m for m in models_list if m != expensive]
                if others:
                    cheap = others[0]
            if cheap and expensive and cheap != expensive:
                auto_cfg = {"complex_model": expensive, "simple_model": cheap}
                # Persist to config file
                try:
                    from openagentic.core.llm.provider_config import get_provider_store
                    store = get_provider_store()
                    store.set_automodel(provider, auto_cfg)
                    model = cheap
                    am_cfg = auto_cfg
                except Exception as exc:
                    logger.warning(
                        "automodel auto-config persist failed (provider=%s): %s",
                        provider, exc, exc_info=True,
                    )

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
        logger.warning("skills seeding failed: %s", exc, exc_info=True)

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
    _console.print(f"  [dim]Type /help for commands.[/dim]")
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
                if len(messages) > 3:
                    try:
                        from openagentic.memory.manager import MemoryManager
                        from datetime import datetime, timezone
                        mgr = MemoryManager()
                        title = f"会话 {datetime.now(timezone.utc).strftime('%m-%d %H:%M')}"
                        summary_lines = []
                        for m in messages[-20:]:
                            role = m.get("role", "?")
                            content = (m.get("content") or "")[:200]
                            if content:
                                summary_lines.append(f"[{role}] {content}")
                        if summary_lines:
                            mgr.save_episode(title, "\n".join(summary_lines[-10:]), ["conversation"])
                    except Exception as exc:
                        logger.warning("auto-save episode on /clear failed: %s", exc, exc_info=True)
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
                base = (plat["base"] or "").strip()
                if not base:
                    input_gate.clear()
                    try:
                        base = (await session.prompt_async(
                            "  Server URL (e.g. http://127.0.0.1:8000): "
                        )).strip()
                    except (EOFError, KeyboardInterrupt):
                        input_gate.set()
                        continue
                    input_gate.set()
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
                elif arg == "setup":
                    if setup_automodel_interactive(provider):
                        automodel_enabled = True
                        _console.print("  [green]automodel ON[/green]")
                    continue
                else:
                    _console.print("  [red]Usage: /automodel on|off|setup[/red]")
                    continue

            if user_input == "/skills" or user_input.startswith("/skills "):
                from openagentic.skills import SkillsManager, SkillNotFound, SkillError
                mgr = SkillsManager()
                args = user_input[len("/skills"):].strip()

                if not args:
                    skills, errors = mgr.list_with_errors()
                    _console.print()
                    if not skills and not errors:
                        _console.print("  [dim]还没有 skill。`/skills new <name>` 创建一个。[/dim]")
                    for s in skills:
                        _console.print(f"  [bold cyan]{s.slug}[/bold cyan]  {s.description}")
                    for path, err in errors:
                        _console.print(f"  [red]✗ {path}: {err}[/red]")
                    _console.print()
                    continue

                parts = args.split(maxsplit=1)
                sub = parts[0]

                if sub == "reload":
                    # 解析在 list_with_errors 内每次都重扫，无需缓存——这里只是给用户反馈
                    skills, errors = mgr.list_with_errors()
                    _console.print(f"\n  [green]reloaded:[/green] {len(skills)} skill(s), {len(errors)} error(s)")
                    rebuild_system_message()
                    _console.print()
                    continue

                if sub == "new":
                    if len(parts) < 2 or not parts[1].strip():
                        _console.print("  [red]Usage: /skills new <slug>[/red]")
                        continue
                    new_slug = parts[1].strip()
                    try:
                        path = mgr.create_template(new_slug)
                    except SkillError as exc:
                        _console.print(f"  [red]{exc}[/red]")
                        continue
                    _console.print(f"\n  [green]created:[/green] {path}")
                    _console.print("  [dim]编辑后用 /skills reload 重新加载。[/dim]\n")
                    continue

                # 视为 /skills <slug> —— 显示该 skill 详情
                target_slug = sub
                try:
                    skill = mgr.get(target_slug)
                except SkillNotFound as exc:
                    _console.print(f"  [red]{exc}[/red]")
                    continue
                _console.print()
                _console.print(f"  [bold cyan]{skill.slug}[/bold cyan]  {skill.path}")
                _console.print(f"  [dim]{skill.description}[/dim]")
                if skill.allowed_tools:
                    _console.print(f"  [dim]allowed-tools:[/dim] {', '.join(skill.allowed_tools)}")
                _console.print()
                _console.print(skill.body.rstrip())
                _console.print()
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

            # ── LLM triage auto-routing ──
            current_model = model
            routed_model, hint = await route_model(
                user_input,
                provider,
                current_model,
                api_base,
                api_key,
                automodel_enabled=automodel_enabled,
            )
            if hint:
                _console.print(f"  [dim]{hint}[/dim]")
            if routed_model != current_model:
                model = routed_model
                rebuild_system_message()

            # ── Execute react loop（包成 task，让 producer 的 Ctrl+C 能取消）──
            react_task = asyncio.create_task(
                react_loop(
                    user_input,
                    messages,
                    model,
                    api_base,
                    api_key,
                    platform_api_base=plat["base"],
                    platform_user_email=plat["email"],
                    confirm_fn=_confirm_fn,
                )
            )
            react_task_ref["task"] = react_task
            try:
                await react_task
            except asyncio.CancelledError:
                _console.print(
                    "\n  [yellow]已中断本轮（Ctrl+C）。会话保留，可继续输入；再按一次 Ctrl+C 退出。[/yellow]"
                )
            except Exception as e:
                _console.print(f"\n  [red bold]Error:[/red bold] {type(e).__name__}: {e}")
            finally:
                react_task_ref["task"] = None

            # After execution, reset model back to simple_model for next triage
            if routed_model != current_model and automodel_enabled:
                from openagentic.cli.model_router import _get_automodel_config
                am_cfg = _get_automodel_config(provider)
                if am_cfg and am_cfg.get("simple_model"):
                    model = am_cfg["simple_model"]
                    rebuild_system_message()

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
