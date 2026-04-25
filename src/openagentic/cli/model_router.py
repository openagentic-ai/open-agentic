"""两级模型自动路由模块 — LLM triage 模式。

所有请求先发给 simple_model（便宜/快），由它判断任务复杂度：
- 简单任务 → simple_model 直接回答
- 复杂任务 → 切换到 complex_model 回答，完成后下一轮自动切回 simple_model

配置保存在 `.openagentic/model_providers.json` 的 `automodel` 字段：

    {
      "id": "deepseek",
      "automodel": {
        "complex_model": "deepseek/deepseek-v4-pro",
        "simple_model": "deepseek/deepseek-v4-flash"
      }
    }
"""

from __future__ import annotations

from typing import Any

import litellm

from rich.console import Console

from openagentic.cli._patchable_stdout import _patchable_stdout

_console = Console(file=_patchable_stdout)

# ── Triage prompt: ask the cheap model to classify ──

_TRIAGE_SYSTEM = (
    "You are a task complexity classifier. "
    "Given the user's message, decide if this is a SIMPLE or COMPLEX task.\n\n"
    "SIMPLE: greetings, chitchat, factual Q&A, explanations, translations, summaries, "
    "short lookups, simple file reads.\n"
    "COMPLEX: writing/modifying code, debugging, architecture design, multi-step operations, "
    "refactoring, performance optimization, security analysis, system design, "
    "any task requiring deep reasoning or multiple tool calls.\n\n"
    "Respond with EXACTLY one word: SIMPLE or COMPLEX. Nothing else."
)


def _get_automodel_config(provider: str) -> dict[str, Any] | None:
    """Read automodel config for a provider from model_providers.json."""
    try:
        from openagentic.core.llm.provider_config import get_provider_store
        store = get_provider_store().get()
        for profile in store.profiles:
            if profile.id == provider and profile.enabled:
                raw = getattr(profile, "automodel", None)
                if raw and isinstance(raw, dict):
                    return raw
        return None
    except Exception:
        return None


async def triage_classify(
    user_input: str,
    simple_model: str,
    api_base: str | None,
    api_key: str | None,
) -> str:
    """Ask the simple model to classify task complexity.

    Returns 'complex' or 'simple'. Defaults to 'simple' on any error.
    """
    try:
        resp = await litellm.acompletion(
            model=simple_model,
            messages=[
                {"role": "system", "content": _TRIAGE_SYSTEM},
                {"role": "user", "content": user_input},
            ],
            temperature=0,
            max_tokens=10,
            api_base=api_base or None,
            api_key=api_key or None,
            timeout=15,
        )
        answer = (resp.choices[0].message.content or "").strip().upper()
        if "COMPLEX" in answer:
            return "complex"
        return "simple"
    except Exception:
        return "simple"


async def route_model(
    user_input: str,
    provider: str,
    current_model: str,
    api_base: str | None,
    api_key: str | None,
    *,
    automodel_enabled: bool = True,
) -> tuple[str, str | None]:
    """Route to appropriate model using LLM triage.

    Sends user input to the simple model for classification.
    If complex, returns the complex model. Otherwise returns simple model.

    Returns:
        (model_to_use, hint_message_or_None)
    """
    if not automodel_enabled:
        return current_model, None

    config = _get_automodel_config(provider)
    if not config:
        return current_model, None

    complex_model = config.get("complex_model", "")
    simple_model = config.get("simple_model", "")
    if not complex_model or not simple_model:
        return current_model, None

    classification = await triage_classify(user_input, simple_model, api_base, api_key)
    target_model = complex_model if classification == "complex" else simple_model

    if target_model == current_model:
        return current_model, None

    short = target_model.split("/")[-1] if "/" in target_model else target_model
    hint = f"[auto -> {short}]"
    return target_model, hint


def automodel_status(provider: str, automodel_enabled: bool) -> str:
    """Return /automodel status description."""
    state = "ON" if automodel_enabled else "OFF"
    config = _get_automodel_config(provider)
    if not config:
        return f"/automodel: {state} (not configured for '{provider}' — run /automodel setup)"

    complex_m = config.get("complex_model", "?").split("/")[-1]
    simple_m = config.get("simple_model", "?").split("/")[-1]
    return (
        f"/automodel: {state}\n"
        f"  triage: {simple_m} classifies -> simple stays on {simple_m}, complex escalates to {complex_m}"
    )


# ---------------------------------------------------------------------------
# Interactive setup
# ---------------------------------------------------------------------------

def _get_configured_providers() -> list[dict[str, Any]]:
    """Get all providers that have API keys configured."""
    try:
        from openagentic.core.llm.provider_config import get_provider_store
        store = get_provider_store().get()
        result = []
        for p in store.profiles:
            if p.enabled and p.api_key:
                result.append({
                    "id": p.id,
                    "display_name": p.display_name,
                    "models": list(p.models),
                    "has_automodel": p.automodel is not None,
                })
        return result
    except Exception:
        return []


def setup_automodel_interactive(current_provider: str) -> bool:
    """Interactive automodel setup. Returns True if config was saved."""
    providers = _get_configured_providers()

    if not providers:
        _console.print("  [yellow]No providers with API keys configured.[/yellow]")
        _console.print("  [dim]Use /provider-config to add an API key first.[/dim]")
        return False

    # Select provider
    current_in_list = [p for p in providers if p["id"] == current_provider]

    if len(providers) == 1:
        target = providers[0]
        _console.print(f"\n  Provider: [bold]{target['display_name']}[/bold]")
    else:
        _console.print(f"\n  [bold]Providers with API keys:[/bold]")
        for i, p in enumerate(providers, 1):
            mark = " [green]<-[/green]" if p["id"] == current_provider else ""
            configured = " [dim](automodel configured)[/dim]" if p["has_automodel"] else ""
            _console.print(f"    {i}. {p['display_name']} ({p['id']}){mark}{configured}")

        _console.print()
        try:
            choice = input("  Select provider (number or Enter for current): ").strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if not choice:
            target = current_in_list[0] if current_in_list else providers[0]
        elif choice.isdigit() and 1 <= int(choice) <= len(providers):
            target = providers[int(choice) - 1]
        else:
            _console.print(f"  [red]Invalid choice.[/red]")
            return False

    models = target["models"]
    if len(models) < 2:
        _console.print(f"  [yellow]{target['display_name']} only has {len(models)} model(s).[/yellow]")
        _console.print("  [dim]Need at least 2 models. Add more via /provider-config.[/dim]")
        return False

    # Show models
    _console.print(f"\n  [bold]{target['display_name']}[/bold] models:")
    for i, m in enumerate(models, 1):
        short = m.split("/")[-1] if "/" in m else m
        _console.print(f"    {i}. {short}")

    _console.print()
    _console.print("  [bold]How it works:[/bold]")
    _console.print("  All requests go to the [cyan]simple[/cyan] (cheap) model first.")
    _console.print("  It classifies the task. Complex tasks escalate to the [cyan]complex[/cyan] (powerful) model.")
    _console.print()

    try:
        c_input = input(f"  complex (powerful/expensive) model (1-{len(models)}): ").strip()
        if not c_input.isdigit() or not (1 <= int(c_input) <= len(models)):
            _console.print("  [red]Cancelled.[/red]")
            return False
        complex_model = models[int(c_input) - 1]

        s_input = input(f"  simple (cheap/fast) model (1-{len(models)}): ").strip()
        if not s_input.isdigit() or not (1 <= int(s_input) <= len(models)):
            _console.print("  [red]Cancelled.[/red]")
            return False
        simple_model = models[int(s_input) - 1]
    except (EOFError, KeyboardInterrupt):
        return False

    if complex_model == simple_model:
        _console.print("  [yellow]Same model for both roles — automodel won't route.[/yellow]")

    # Save
    automodel_cfg = {
        "complex_model": complex_model,
        "simple_model": simple_model,
    }

    try:
        from openagentic.core.llm.provider_config import get_provider_store
        store = get_provider_store()
        store.set_automodel(target["id"], automodel_cfg)
    except Exception as e:
        _console.print(f"  [red]Failed to save: {e}[/red]")
        return False

    c_short = complex_model.split("/")[-1] if "/" in complex_model else complex_model
    s_short = simple_model.split("/")[-1] if "/" in simple_model else simple_model
    _console.print()
    _console.print(f"  [green]Saved![/green]")
    _console.print(f"  {s_short} [dim](triage + simple tasks)[/dim]")
    _console.print(f"  {c_short} [dim](complex tasks)[/dim]")
    return True
