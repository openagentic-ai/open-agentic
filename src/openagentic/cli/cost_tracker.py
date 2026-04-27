"""Per-process token usage / cost accumulator for the CLI session.

LiteLLM responses carry `usage` (OpenAI-style prompt/completion/total tokens)
and `litellm.completion_cost` looks up the model registry to estimate dollar
cost. Both are best-effort: local providers (Ollama) and unknown models simply
report 0 cost — that is fine, the CLI prints "—" so users aren't misled.

Recording happens inside `litellm_chat`; `/cost` reads `summary()`; `/clear`
calls `reset()`.
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = structlog.get_logger(__name__)


@dataclass
class _ModelTotals:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cost_known: bool = False  # False if every call returned 0 from completion_cost


@dataclass
class _SessionTotals:
    by_model: dict[str, _ModelTotals] = field(default_factory=dict)


_state = _SessionTotals()
_lock = Lock()


def record(model: str, response: Any) -> None:
    """Accumulate one LLM call's usage. Safe to call with anything; failures
    are logged at warning and never raise — cost tracking must not break chat.
    """
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))

        cost = 0.0
        cost_known = False
        try:
            import litellm
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
            cost_known = cost > 0
        except Exception as exc:
            logger.debug("completion_cost failed", model=model, error=str(exc))

        with _lock:
            entry = _state.by_model.setdefault(model, _ModelTotals())
            entry.calls += 1
            entry.prompt_tokens += prompt
            entry.completion_tokens += completion
            entry.total_tokens += total
            entry.cost_usd += cost
            if cost_known:
                entry.cost_known = True
    except Exception as exc:  # never break chat
        logger.warning("cost_tracker.record failed", error=str(exc), exc_info=True)


def summary() -> dict[str, Any]:
    """Snapshot of the session totals — safe to call at any time."""
    with _lock:
        models = []
        agg_calls = 0
        agg_prompt = 0
        agg_completion = 0
        agg_total = 0
        agg_cost = 0.0
        any_cost_known = False
        for name, t in _state.by_model.items():
            models.append({
                "model": name,
                "calls": t.calls,
                "prompt_tokens": t.prompt_tokens,
                "completion_tokens": t.completion_tokens,
                "total_tokens": t.total_tokens,
                "cost_usd": t.cost_usd,
                "cost_known": t.cost_known,
            })
            agg_calls += t.calls
            agg_prompt += t.prompt_tokens
            agg_completion += t.completion_tokens
            agg_total += t.total_tokens
            agg_cost += t.cost_usd
            any_cost_known = any_cost_known or t.cost_known
    models.sort(key=lambda m: m["total_tokens"], reverse=True)
    return {
        "by_model": models,
        "totals": {
            "calls": agg_calls,
            "prompt_tokens": agg_prompt,
            "completion_tokens": agg_completion,
            "total_tokens": agg_total,
            "cost_usd": agg_cost,
            "cost_known": any_cost_known,
        },
    }


def reset() -> None:
    """Clear all accumulated usage. Called on /clear so a new session starts
    from zero — otherwise users can't tell which session a number belongs to.
    """
    with _lock:
        _state.by_model.clear()
