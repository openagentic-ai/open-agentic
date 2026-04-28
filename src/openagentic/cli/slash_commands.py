"""Slash-command handlers, completer, and prompt UI primitives.

Pulled out of ``repl.py`` so the main producer/consumer loop stays focused on
concurrency. Each ``_handle_*`` is independently testable; ``main_loop`` only
dispatches by name.
"""

from __future__ import annotations

import asyncio
import structlog
import shutil
import subprocess

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.syntax import Syntax

from openagentic.cli._patchable_stdout import _patchable_stdout
from openagentic.cli.auth import platform_authenticate_sync
from openagentic.cli.model_router import route_model
from openagentic.cli.providers import find_profile
from openagentic.cli.react import react_loop

logger = structlog.get_logger(__name__)
_console = Console(file=_patchable_stdout)

# Sentinel pushed onto the input queue to tell the consumer to exit cleanly.
_SENTINEL_QUIT = object()

SLASH_COMMANDS = [
    "/help", "/config", "/model", "/provider", "/providers",
    "/provider-config", "/automodel", "/clear",
    "/skills",
    "/compact", "/context", "/btw", "/cost", "/permissions",
    "/diff", "/review",
    "/login-platform", "/logout-platform", "/quit",
]


# ---------------------------------------------------------------------------
# Slash command handlers
# ---------------------------------------------------------------------------


async def _handle_compact(
    messages: list[dict],
    model: str,
    api_base: str | None,
    api_key: str | None,
) -> None:
    """Force-compress working memory now."""
    from openagentic.memory.manager import compress_working_memory, estimate_tokens
    before = estimate_tokens(messages)
    if len(messages) <= 12:
        _console.print(
            f"  [dim]当前 {len(messages)} 条消息 / ~{before} token，"
            "数量太少，无需压缩。[/dim]"
        )
        return
    try:
        new_messages = await compress_working_memory(
            messages, model=model, api_base=api_base, api_key=api_key,
        )
        messages[:] = new_messages
        after = estimate_tokens(messages)
        _console.print(
            f"  [green]compacted:[/green] {before} → {after} token "
            f"({len(messages)} 条消息)"
        )
    except Exception as exc:
        _console.print(f"  [red]compact failed: {exc}[/red]")


def _handle_context(messages: list[dict]) -> None:
    """Show context window usage stats."""
    from openagentic.memory.manager import estimate_tokens
    total = estimate_tokens(messages)
    sys_len = len(messages[0].get("content") or "") if messages else 0
    roles: dict[str, int] = {}
    for m in messages:
        r = m.get("role", "?")
        roles[r] = roles.get(r, 0) + 1
    _console.print()
    _console.print(f"  [bold]messages:[/bold] {len(messages)} 条")
    _console.print(
        "  [bold]by role:[/bold] "
        + ", ".join(f"{r}={n}" for r, n in roles.items())
    )
    _console.print(f"  [bold]system prompt:[/bold] {sys_len} 字符")
    _console.print(f"  [bold]est. tokens:[/bold] ~{total}")
    _console.print("  [dim]auto-compact 阈值: 6000 token[/dim]")
    _console.print()


def _handle_cost() -> None:
    """Show per-model token usage + estimated USD cost for this session.

    Cost comes from `litellm.completion_cost`; for local providers (Ollama)
    or models missing from the registry it stays 0 — we render "—" so the
    user is not misled into thinking a real call was free.
    """
    from openagentic.cli import cost_tracker
    snap = cost_tracker.summary()
    totals = snap["totals"]
    _console.print()
    if totals["calls"] == 0:
        _console.print("  [dim]本会话尚无 LLM 调用记录。[/dim]")
        _console.print()
        return
    _console.print(
        f"  [bold]calls:[/bold] {totals['calls']}   "
        f"[bold]tokens:[/bold] {totals['total_tokens']} "
        f"(prompt {totals['prompt_tokens']} / completion {totals['completion_tokens']})"
    )
    if totals["cost_known"]:
        _console.print(f"  [bold]est. cost:[/bold] ${totals['cost_usd']:.6f} USD")
    else:
        _console.print(
            "  [bold]est. cost:[/bold] — [dim](无法估算：本地模型或定价表缺失)[/dim]"
        )
    _console.print()
    _console.print("  [bold]by model:[/bold]")
    for m in snap["by_model"]:
        cost_str = (
            f"${m['cost_usd']:.6f}" if m["cost_known"] else "—"
        )
        _console.print(
            f"    {m['model']}  calls={m['calls']}  "
            f"tokens={m['total_tokens']} (in {m['prompt_tokens']} / out {m['completion_tokens']})  "
            f"cost={cost_str}"
        )
    _console.print()


def _handle_permissions(args: str) -> None:  # noqa: C901
    """Inspect and mutate the per-tool permission policy.

    Subcommands chosen to fit one-line shell muscle memory:
        /permissions
        /permissions set <tool> <allow|ask|deny>
        /permissions allow-path <tool> <path>
        /permissions deny-path  <tool> <path>
        /permissions allow-prefix run_command <prefix>
        /permissions deny-prefix  run_command <prefix>
        /permissions reset
    """
    from openagentic.cli import permissions as perm

    args = args.strip()

    if not args:
        cfg = perm.load()
        _console.print()
        _console.print("  [bold]permissions:[/bold]")
        for tool in perm.GATED_TOOLS:
            p = cfg.tools[tool]
            _console.print(f"    [cyan]{tool}[/cyan]  policy=[bold]{p.policy}[/bold]")
            if p.allow_paths:
                _console.print(f"      allow_paths: {p.allow_paths}")
            if p.deny_paths:
                _console.print(f"      deny_paths:  {p.deny_paths}")
            if p.allow_prefixes:
                _console.print(f"      allow_prefixes: {p.allow_prefixes}")
            if p.deny_prefixes:
                _console.print(f"      deny_prefixes:  {p.deny_prefixes}")
        _console.print()
        _console.print(f"  [dim]config: {perm._config_path()}[/dim]")
        _console.print()
        return

    parts = args.split()
    sub = parts[0]

    if sub == "reset":
        cfg = perm._build_default()
        path = perm.save(cfg)
        _console.print(f"  [green]permissions reset to defaults → {path}[/green]")
        return

    if sub == "set" and len(parts) == 3:
        tool, policy = parts[1], parts[2]
        if tool not in perm.GATED_TOOLS:
            _console.print(f"  [red]unknown tool: {tool}[/red] (need {list(perm.GATED_TOOLS)})")
            return
        if policy not in perm.POLICIES:
            _console.print(f"  [red]invalid policy: {policy}[/red] (need {list(perm.POLICIES)})")
            return
        cfg = perm.load()
        cfg.tools[tool].policy = policy
        perm.save(cfg)
        _console.print(f"  [green]{tool}.policy → {policy}[/green]")
        return

    if sub in ("allow-path", "deny-path") and len(parts) >= 3:
        tool = parts[1]
        path = " ".join(parts[2:])
        if tool not in perm.GATED_TOOLS:
            _console.print(f"  [red]unknown tool: {tool}[/red]")
            return
        if tool == "run_command":
            _console.print("  [red]run_command 不接受 path，请用 allow-prefix / deny-prefix[/red]")
            return
        cfg = perm.load()
        target = cfg.tools[tool].allow_paths if sub == "allow-path" else cfg.tools[tool].deny_paths
        if path not in target:
            target.append(path)
            perm.save(cfg)
        _console.print(f"  [green]{tool}.{sub.replace('-', '_')}s += {path}[/green]")
        return

    if sub in ("allow-prefix", "deny-prefix") and len(parts) >= 3:
        tool = parts[1]
        prefix = " ".join(parts[2:])
        if tool != "run_command":
            _console.print("  [red]allow-prefix / deny-prefix 仅用于 run_command[/red]")
            return
        cfg = perm.load()
        target = (
            cfg.tools[tool].allow_prefixes
            if sub == "allow-prefix"
            else cfg.tools[tool].deny_prefixes
        )
        if prefix not in target:
            target.append(prefix)
            perm.save(cfg)
        _console.print(f"  [green]{tool}.{sub.replace('-', '_')}es += {prefix!r}[/green]")
        return

    _console.print(
        "  [red]Usage:[/red]\n"
        "    /permissions\n"
        "    /permissions set <tool> <allow|ask|deny>\n"
        "    /permissions allow-path <tool> <path>\n"
        "    /permissions deny-path  <tool> <path>\n"
        "    /permissions allow-prefix run_command <prefix>\n"
        "    /permissions deny-prefix  run_command <prefix>\n"
        "    /permissions reset"
    )


def _handle_btw(messages: list[dict], note: str) -> None:
    """Append a note to the message list without triggering inference."""
    messages.append({"role": "user", "content": note})
    preview = note[:100] + ("..." if len(note) > 100 else "")
    _console.print(f"  [green]noted:[/green] {preview}")
    _console.print("  [dim](已加入对话上下文，未触发推理)[/dim]")


def _handle_clear(messages: list[dict], rebuild_system_message) -> None:
    """Archive the tail of the session as an episode, then reset history & cost.

    The archive is best-effort — failure logs but doesn't block the clear,
    because the user's intent is "wipe state now".
    """
    if len(messages) > 3:
        try:
            from datetime import datetime, timezone
            from openagentic.memory.manager import MemoryManager
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
            logger.warning("auto-save episode on /clear failed", error=str(exc), exc_info=True)
    messages.clear()
    messages.append({"role": "system", "content": ""})
    rebuild_system_message()
    from openagentic.cli import cost_tracker
    cost_tracker.reset()
    _console.print("[green]  history cleared[/green] [dim](cost counter reset)[/dim]")


def _handle_skills_cmd(args: str, rebuild_system_message) -> None:
    """Dispatch /skills sub-commands (list / reload / new / show)."""
    from openagentic.skills import SkillsManager, SkillNotFound, SkillError
    mgr = SkillsManager()

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
        return

    parts = args.split(maxsplit=1)
    sub = parts[0]

    if sub == "reload":
        # 解析在 list_with_errors 内每次都重扫，无需缓存——这里只是给用户反馈
        skills, errors = mgr.list_with_errors()
        _console.print(f"\n  [green]reloaded:[/green] {len(skills)} skill(s), {len(errors)} error(s)")
        rebuild_system_message()
        _console.print()
        return

    if sub == "new":
        if len(parts) < 2 or not parts[1].strip():
            _console.print("  [red]Usage: /skills new <slug>[/red]")
            return
        new_slug = parts[1].strip()
        try:
            path = mgr.create_template(new_slug)
        except SkillError as exc:
            _console.print(f"  [red]{exc}[/red]")
            return
        _console.print(f"\n  [green]created:[/green] {path}")
        _console.print("  [dim]编辑后用 /skills reload 重新加载。[/dim]\n")
        return

    # 视为 /skills <slug> —— 显示该 skill 详情
    target_slug = sub
    try:
        skill = mgr.get(target_slug)
    except SkillNotFound as exc:
        _console.print(f"  [red]{exc}[/red]")
        return
    _console.print()
    _console.print(f"  [bold cyan]{skill.slug}[/bold cyan]  {skill.path}")
    _console.print(f"  [dim]{skill.description}[/dim]")
    if skill.allowed_tools:
        _console.print(f"  [dim]allowed-tools:[/dim] {', '.join(skill.allowed_tools)}")
    _console.print()
    _console.print(skill.body.rstrip())
    _console.print()


def _apply_automodel_defaults(provider: str, model: str) -> str:
    """Pick the cheap (simple) model for *provider* if automodel is configured
    or can be auto-inferred from name conventions (`flash`/`mini` ↔ `pro`/`max`).

    Returns the model that should be used to start the session — either the
    configured/inferred simple_model, or *model* unchanged. Side-effect: when
    we infer a fresh pair, persist it so future sessions don't redo the work.
    """
    from openagentic.cli.model_router import _get_automodel_config
    am_cfg = _get_automodel_config(provider)
    if am_cfg and am_cfg.get("simple_model"):
        return am_cfg["simple_model"]

    profile = find_profile(provider)
    models_list = profile["models"] if profile else []
    if len(models_list) < 2:
        return model

    # Try to auto-detect cheap/expensive model pairs by naming convention
    cheap_kw = ["flash", "mini", "lite", "nano", "tiny", "small", "fast"]
    exp_kw = ["pro", "max", "ultra", "large", "premium", "op"]
    cheap = next((m for m in models_list if any(k in m.lower() for k in cheap_kw)), None)
    expensive = next((m for m in models_list if any(k in m.lower() for k in exp_kw)), None)
    # If only one direction found, infer the other from the remaining models
    if cheap and not expensive:
        others = [m for m in models_list if m != cheap]
        if others:
            expensive = others[0]
    elif expensive and not cheap:
        others = [m for m in models_list if m != expensive]
        if others:
            cheap = others[0]

    if not (cheap and expensive and cheap != expensive):
        return model

    auto_cfg = {"complex_model": expensive, "simple_model": cheap}
    # Persist to config file
    try:
        from openagentic.core.llm.provider_config import get_provider_store
        get_provider_store().set_automodel(provider, auto_cfg)
        return cheap
    except Exception as exc:
        logger.warning(
            "automodel auto-config persist failed",
            provider=provider, error=str(exc), exc_info=True,
        )
        return model


async def _handle_login_platform(
    plat: dict,
    session: PromptSession,
    input_gate: asyncio.Event,
    rebuild_system_message,
) -> None:
    """Prompt for server URL if missing, run platform auth, store token."""
    base = (plat["base"] or "").strip()
    if not base:
        input_gate.clear()
        try:
            base = (await session.prompt_async(
                "  Server URL (e.g. http://127.0.0.1:8000): "
            )).strip()
        except (EOFError, KeyboardInterrupt):
            input_gate.set()
            return
        input_gate.set()
    if not base:
        _console.print("  [red]URL required.[/red]")
        return
    plat["base"] = base.rstrip("/")
    tok, em = platform_authenticate_sync(plat["base"])
    plat["token"] = tok
    plat["email"] = em
    rebuild_system_message()
    _console.print(f"  [green]Logged in:[/green] {em}")


async def _run_react_turn(
    user_input: str,
    messages: list[dict],
    *,
    provider: str,
    model: str,
    api_base: str | None,
    api_key: str | None,
    automodel_enabled: bool,
    plat: dict,
    confirm_fn,
    react_task_ref: dict,
    rebuild_system_message,
) -> str:
    """One full user turn: triage routing → react_loop (cancelable) → reset
    routed model. Returns the model name to keep for the next turn.

    The model rotation logic lives here so the consumer loop doesn't need to
    know about automodel internals.
    """
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
            confirm_fn=confirm_fn,
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

    return model


def _handle_diff(args: str) -> None:
    """Wrap `git diff` with rich syntax highlighting.

    Supports optional path and flags:
        /diff                  → unstaged changes (working tree vs index)
        /diff --staged         → staged changes (index vs HEAD)
        /diff <path>           → filter to specific file/directory
        /diff --staged <path>  → combine flags and path
    """
    cmd = ["git", "diff"]
    # 用户可追加任意 git diff 参数（如 --staged / --cached / HEAD~1）
    if args.strip():
        cmd.extend(args.strip().split())
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        _console.print("  [red]git not found. Is git installed?[/red]")
        return
    except subprocess.TimeoutExpired:
        _console.print("  [red]git diff timed out (30s).[/red]")
        return

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            from rich.markup import escape
            _console.print(f"  [red]git diff failed:[/red] {escape(stderr)}")
        return

    output = result.stdout
    if not output.strip():
        _console.print("  [dim]No changes (working tree clean).[/dim]")
        return

    _console.print()
    # rich Syntax 自动给 diff 着色（+绿/-红/@@青）
    syntax = Syntax(output, "diff", theme="monokai", line_numbers=False)
    _console.print(syntax)
    _console.print()


async def _handle_review(
    args: str,
    queue: asyncio.Queue,
) -> None:
    """Gather `git diff` and inject a code-review request into the conversation.

    The diff is formatted as a user message that triggers the code-review skill:
        /review                  → review unstaged changes
        /review --staged         → review staged changes
        /review <path>           → review specific file/dir
        /review --staged <path>  → combine flags and path
    """
    cmd = ["git", "diff"]
    if args.strip():
        cmd.extend(args.strip().split())
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        _console.print("  [red]git not found. Is git installed?[/red]")
        return
    except subprocess.TimeoutExpired:
        _console.print("  [red]git diff timed out (30s).[/red]")
        return

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            from rich.markup import escape
            _console.print(f"  [red]git diff failed:[/red] {escape(stderr)}")
        return

    output = result.stdout
    if not output.strip():
        _console.print("  [dim]No changes to review (working tree clean).[/dim]")
        return

    # 截断超大 diff（>500 行），避免撑爆 context
    lines = output.split("\n")
    if len(lines) > 500:
        truncated = "\n".join(lines[:500])
        truncated += f"\n\n... (truncated {len(lines) - 500} lines, showing first 500)"
        output = truncated

    prompt = (
        "Please review the following changes using the code-review skill:\n\n"
        f"```diff\n{output}\n```"
    )
    await queue.put(prompt)
    _console.print(
        f"  [green]diff injected[/green] [dim]({len(lines)} lines, triggering code-review)[/dim]"
    )


# ---------------------------------------------------------------------------
# UI primitives — completer, help text, prompt/toolbar renderers
# ---------------------------------------------------------------------------


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
    _console.print(
        "  /compact  /context  /btw <text>  /cost"
    )
    _console.print(
        "  /diff [path]  /review [path]"
    )
    _console.print(
        "  /permissions [set|allow-path|deny-path|allow-prefix|deny-prefix|reset]"
    )
    _console.print()
    _console.print("[bold]Tips[/bold]")
    _console.print("  write_file / delete_file need Y/N confirmation before execution")
    _console.print("  /btw <text> 仅追加到对话上下文，不触发推理（高频备注/补充用）")
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
