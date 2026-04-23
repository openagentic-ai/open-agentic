"""Boundary tests for CLI input handling and provider selection."""

from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from openagentic.cli import providers


def test_sanitize_cli_input_removes_ansi_escape_sequences():
    value = "abc\x1b[Adef\x1b[2K"
    assert providers._sanitize_cli_input(value) == "abcdef"


def test_sanitize_cli_input_removes_caret_escape_and_control_chars():
    value = "x^[[By\x07z"
    assert providers._sanitize_cli_input(value) == "xyz"


def test_prompt_input_drains_buffer_and_trims(monkeypatch):
    calls = {"ensure": 0, "drain": 0}

    monkeypatch.setattr(providers.CLI_PLATFORM, "ensure_line_input_mode", lambda: calls.__setitem__("ensure", calls["ensure"] + 1))
    monkeypatch.setattr(
        providers.CLI_PLATFORM,
        "drain_stdin_buffer",
        lambda settle_ms=0: calls.__setitem__("drain", calls["drain"] + 1),
    )
    monkeypatch.setattr(builtins, "input", lambda _p: "  hi^[[B  ")

    result = providers._prompt_input(">")
    assert result == "hi"
    assert calls["ensure"] == 1
    assert calls["drain"] == 1


def test_prompt_secret_input_uses_getpass(monkeypatch):
    monkeypatch.setattr(providers.CLI_PLATFORM, "ensure_line_input_mode", lambda: None)
    monkeypatch.setattr(providers.CLI_PLATFORM, "drain_stdin_buffer", lambda settle_ms=0: None)
    monkeypatch.setattr(providers.getpass, "getpass", lambda _p: "sk-abc^[[A")

    assert providers._prompt_secret_input("API Key: ") == "sk-abc"


def test_prompt_secret_input_falls_back_to_input_on_getpass_error(monkeypatch):
    monkeypatch.setattr(providers.CLI_PLATFORM, "ensure_line_input_mode", lambda: None)
    monkeypatch.setattr(providers.CLI_PLATFORM, "drain_stdin_buffer", lambda settle_ms=0: None)

    def _raise(_p):
        raise RuntimeError("tty error")

    monkeypatch.setattr(providers.getpass, "getpass", _raise)
    monkeypatch.setattr(builtins, "input", lambda _p: " fallback^[[B ")

    assert providers._prompt_secret_input("API Key: ") == "fallback"


def test_select_provider_interactive_empty_keeps_current(monkeypatch):
    monkeypatch.setattr(providers.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(
        providers,
        "list_provider_profiles",
        lambda: [
            {"id": "openai", "display_name": "OpenAI", "enabled": True, "api_key": "", "models": [], "api_base": ""},
            {"id": "deepseek", "display_name": "DeepSeek", "enabled": True, "api_key": "sk-x", "models": [], "api_base": ""},
        ],
    )
    monkeypatch.setattr(providers, "_prompt_input", lambda _p: "")
    assert providers.select_provider_interactive("openai") == "openai"


def test_select_provider_interactive_q_returns_none(monkeypatch):
    monkeypatch.setattr(providers.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(
        providers,
        "list_provider_profiles",
        lambda: [{"id": "openai", "display_name": "OpenAI", "enabled": True, "api_key": "", "models": [], "api_base": ""}],
    )
    monkeypatch.setattr(providers, "_prompt_input", lambda _p: "q")
    assert providers.select_provider_interactive("openai") is None


def test_select_provider_interactive_numeric_chooses_index(monkeypatch):
    monkeypatch.setattr(providers.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(
        providers,
        "list_provider_profiles",
        lambda: [
            {"id": "openai", "display_name": "OpenAI", "enabled": True, "api_key": "", "models": [], "api_base": ""},
            {"id": "anthropic", "display_name": "Anthropic", "enabled": True, "api_key": "", "models": [], "api_base": ""},
        ],
    )
    monkeypatch.setattr(providers, "_prompt_input", lambda _p: "2")
    assert providers.select_provider_interactive("openai") == "anthropic"


def test_select_provider_interactive_invalid_then_valid(monkeypatch):
    monkeypatch.setattr(providers.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(
        providers,
        "list_provider_profiles",
        lambda: [
            {"id": "openai", "display_name": "OpenAI", "enabled": True, "api_key": "", "models": [], "api_base": ""},
            {"id": "xai", "display_name": "xAI", "enabled": True, "api_key": "", "models": [], "api_base": ""},
        ],
    )
    answers = iter(["99", "xai"])
    monkeypatch.setattr(providers, "_prompt_input", lambda _p: next(answers))
    assert providers.select_provider_interactive("openai") == "xai"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sk-123", True),
        ("x" * 24, True),
        ("too short", False),
        ("", False),
    ],
)
def test_looks_like_api_key_boundaries(value: str, expected: bool):
    assert providers.looks_like_api_key(value) is expected
