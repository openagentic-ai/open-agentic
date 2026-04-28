"""P0 features (Phase 5.5): write_file diff preview, /cost tracker, /permissions.

These cover the contract surface: what behavior the rest of the CLI relies on.
Higher-level slash-command UX is exercised via integration paths in repl tests.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# write_file unified diff preview
# ---------------------------------------------------------------------------


def test_build_unified_diff_shows_changed_lines(tmp_path):
    from openagentic.cli.tools import _build_unified_diff
    f = tmp_path / "x.txt"
    f.write_text("line1\nline2\nline3\n", encoding="utf-8")
    diff = _build_unified_diff(f, "line1\nline2-CHANGED\nline3\n")
    assert "diff:" in diff
    assert "-line2" in diff
    assert "+line2-CHANGED" in diff


def test_build_unified_diff_identical_returns_no_change(tmp_path):
    from openagentic.cli.tools import _build_unified_diff
    f = tmp_path / "x.txt"
    f.write_text("same\n", encoding="utf-8")
    diff = _build_unified_diff(f, "same\n")
    assert "无变化" in diff


def test_build_unified_diff_truncates_long_diff(tmp_path):
    from openagentic.cli.tools import _build_unified_diff, _DIFF_PREVIEW_MAX_LINES
    f = tmp_path / "x.txt"
    f.write_text("\n".join(f"old{i}" for i in range(500)) + "\n", encoding="utf-8")
    new = "\n".join(f"new{i}" for i in range(500)) + "\n"
    diff = _build_unified_diff(f, new)
    # Truncation note must appear once we exceed the cap.
    assert "truncated" in diff
    # Body itself must not blow up the prompt.
    assert diff.count("\n") <= _DIFF_PREVIEW_MAX_LINES + 5


def test_build_unified_diff_handles_binary(tmp_path):
    from openagentic.cli.tools import _build_unified_diff
    f = tmp_path / "x.bin"
    f.write_bytes(b"\xff\xfe\x00\x01")
    diff = _build_unified_diff(f, "text")
    assert "不可用" in diff or "无法" in diff or diff == "" or "diff" not in diff.lower()[:5]


def test_write_file_overwrite_preview_includes_diff(tmp_path):
    """When overwriting, the confirm payload must include a unified diff so
    the user sees exactly what's changing — bytes-only is the bug we're fixing.
    """
    from openagentic.cli import tools
    f = tmp_path / "y.txt"
    f.write_text("hello world\n", encoding="utf-8")

    captured: dict = {}

    async def fake_confirm(title, detail):
        captured["title"] = title
        captured["detail"] = detail
        return False  # refuse so we don't actually write

    asyncio.run(tools.execute_tool(
        "write_file",
        {"path": str(f), "content": "hello WORLD\n"},
        confirm_fn=fake_confirm,
    ))
    assert "diff" in captured["detail"].lower()
    assert "-hello world" in captured["detail"]
    assert "+hello WORLD" in captured["detail"]


# ---------------------------------------------------------------------------
# cost_tracker
# ---------------------------------------------------------------------------


def test_cost_tracker_aggregates_per_model():
    from openagentic.cli import cost_tracker
    cost_tracker.reset()

    fake_resp = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    )
    with mock.patch("litellm.completion_cost", return_value=0.001):
        cost_tracker.record("openai/gpt-4o-mini", fake_resp)
        cost_tracker.record("openai/gpt-4o-mini", fake_resp)
    snap = cost_tracker.summary()
    assert snap["totals"]["calls"] == 2
    assert snap["totals"]["total_tokens"] == 30
    assert abs(snap["totals"]["cost_usd"] - 0.002) < 1e-9
    assert snap["totals"]["cost_known"] is True
    assert snap["by_model"][0]["model"] == "openai/gpt-4o-mini"


def test_cost_tracker_unknown_pricing_marks_unknown():
    from openagentic.cli import cost_tracker
    cost_tracker.reset()
    fake_resp = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    )
    with mock.patch("litellm.completion_cost", side_effect=Exception("no pricing")):
        cost_tracker.record("ollama/qwen3:14b", fake_resp)
    snap = cost_tracker.summary()
    assert snap["totals"]["cost_known"] is False
    assert snap["totals"]["total_tokens"] == 2


def test_cost_tracker_record_swallows_exceptions():
    from openagentic.cli import cost_tracker
    cost_tracker.reset()
    # Object with no .usage at all — must not raise.
    cost_tracker.record("model/x", object())
    snap = cost_tracker.summary()
    assert snap["totals"]["calls"] == 0


def test_cost_tracker_reset_clears_state():
    from openagentic.cli import cost_tracker
    cost_tracker.reset()
    fake_resp = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    )
    with mock.patch("litellm.completion_cost", return_value=0.0):
        cost_tracker.record("m", fake_resp)
    cost_tracker.reset()
    assert cost_tracker.summary()["totals"]["calls"] == 0


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_perms(tmp_path, monkeypatch):
    """Redirect permission storage to a tmp file so tests don't touch ~/."""
    target = tmp_path / "perm.json"
    monkeypatch.setenv("OPENAGENTIC_PERMISSIONS_PATH", str(target))
    return target


def test_permissions_defaults_load_when_missing(isolated_perms):
    from openagentic.cli import permissions as perm
    cfg = perm.load()
    assert cfg.tools["read_file"].policy == "allow"
    assert cfg.tools["run_command"].policy == "allow"
    assert cfg.tools["write_file"].policy == "ask"
    assert cfg.tools["delete_file"].policy == "ask"


def test_permissions_corrupt_file_falls_back_to_defaults(isolated_perms):
    from openagentic.cli import permissions as perm
    isolated_perms.write_text("{ not json", encoding="utf-8")
    cfg = perm.load()
    assert cfg.tools["write_file"].policy == "ask"


def test_permissions_save_then_load_roundtrip(isolated_perms):
    from openagentic.cli import permissions as perm
    cfg = perm.load()
    cfg.tools["run_command"].policy = "deny"
    cfg.tools["run_command"].allow_prefixes = ["git status"]
    perm.save(cfg)
    cfg2 = perm.load()
    assert cfg2.tools["run_command"].policy == "deny"
    assert cfg2.tools["run_command"].allow_prefixes == ["git status"]


def test_permissions_decide_deny_short_circuits(isolated_perms):
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["write_file"].policy = "deny"
    perm.save(cfg)
    decision, _ = perm.decide("write_file", {"path": "/tmp/x"})
    assert decision == perm.DECISION_DENY


def test_permissions_decide_allow_path_overrides_ask(isolated_perms, tmp_path):
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["write_file"].allow_paths = [str(tmp_path)]
    perm.save(cfg)
    target = tmp_path / "sub" / "file.txt"
    decision, _ = perm.decide("write_file", {"path": str(target)})
    assert decision == perm.DECISION_ALLOW


def test_permissions_decide_deny_path_blocks_subdirectory(isolated_perms, tmp_path):
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["write_file"].deny_paths = [str(tmp_path)]
    perm.save(cfg)
    decision, reason = perm.decide(
        "write_file", {"path": str(tmp_path / "sub" / "evil.txt")}
    )
    assert decision == perm.DECISION_DENY
    assert "deny_paths" in reason


def test_permissions_decide_run_command_prefix(isolated_perms):
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["run_command"].policy = "ask"
    cfg.tools["run_command"].allow_prefixes = ["git status"]
    cfg.tools["run_command"].deny_prefixes = ["rm -rf"]
    perm.save(cfg)
    assert perm.decide("run_command", {"command": "git status"})[0] == perm.DECISION_ALLOW
    assert perm.decide("run_command", {"command": "rm -rf /tmp/x"})[0] == perm.DECISION_DENY
    assert perm.decide("run_command", {"command": "echo hi"})[0] == perm.DECISION_ASK


def test_permissions_root_commands_always_ask_even_with_allow_policy(isolated_perms):
    """sudo / doas / pkexec / su must require confirmation even when
    run_command policy is fully `allow` — privilege escalation can never be
    silently approved.
    """
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["run_command"].policy = "allow"
    perm.save(cfg)
    for cmd in ("sudo apt update", "doas pkg upgrade", "pkexec systemctl restart x", "su -", "su"):
        decision, reason = perm.decide("run_command", {"command": cmd})
        assert decision == perm.DECISION_ASK, f"{cmd!r} should force ASK, got {decision}"
        assert "root" in reason


def test_permissions_root_commands_ignore_allow_prefix_whitelist(isolated_perms):
    """Even an explicit allow_prefixes match must NOT bypass root confirmation
    — otherwise a typo in the whitelist becomes a foot-gun.
    """
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["run_command"].policy = "ask"
    cfg.tools["run_command"].allow_prefixes = ["sudo apt-get"]  # user tried to whitelist
    perm.save(cfg)
    decision, _ = perm.decide("run_command", {"command": "sudo apt-get install foo"})
    assert decision == perm.DECISION_ASK


def test_permissions_root_command_deny_still_wins(isolated_perms):
    """If user explicitly denies a sudo prefix, deny still wins over the
    forced-ask rule — explicit deny is the strongest signal.
    """
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["run_command"].deny_prefixes = ["sudo rm"]
    perm.save(cfg)
    decision, _ = perm.decide("run_command", {"command": "sudo rm -rf /"})
    assert decision == perm.DECISION_DENY


def test_permissions_non_root_lookalike_not_forced(isolated_perms):
    """`sudoku` / `surprise` start with `sudo`/`su` letters but aren't root
    commands — must not be over-flagged.
    """
    from openagentic.cli import permissions as perm
    cfg = perm._build_default()
    cfg.tools["run_command"].policy = "allow"
    perm.save(cfg)
    for cmd in ("sudoku --solve", "surprise me"):
        decision, _ = perm.decide("run_command", {"command": cmd})
        assert decision == perm.DECISION_ALLOW, f"{cmd!r} false-positive as root"


def test_permissions_ungated_tool_passes_through(isolated_perms):
    from openagentic.cli import permissions as perm
    decision, _ = perm.decide("done", {})
    assert decision == perm.DECISION_ALLOW


def test_execute_tool_denied_returns_refused(tmp_path, isolated_perms):
    """End-to-end: a deny policy must short-circuit before file IO happens."""
    from openagentic.cli import permissions as perm, tools
    cfg = perm._build_default()
    cfg.tools["write_file"].policy = "deny"
    perm.save(cfg)
    f = tmp_path / "no.txt"
    result = asyncio.run(tools.execute_tool(
        "write_file", {"path": str(f), "content": "hi"},
    ))
    assert result.startswith("[REFUSED]")
    assert not f.exists()


def test_execute_tool_run_sudo_requires_confirm_even_when_allow(isolated_perms):
    """A `sudo ...` command must trigger confirm_fn even when run_command
    policy is `allow` — confirm_fn refusing must short-circuit subprocess.
    """
    from openagentic.cli import permissions as perm, tools

    cfg = perm._build_default()
    cfg.tools["run_command"].policy = "allow"
    perm.save(cfg)

    confirm_called = {"n": 0, "title": ""}

    async def confirm_fn(title, detail):
        confirm_called["n"] += 1
        confirm_called["title"] = title
        return False  # refuse

    with mock.patch("subprocess.run") as m_run:
        result = asyncio.run(tools.execute_tool(
            "run_command", {"command": "sudo whoami"}, confirm_fn=confirm_fn,
        ))
    assert confirm_called["n"] == 1
    assert "root" in confirm_called["title"]
    assert result.startswith("[REFUSED]")
    m_run.assert_not_called()


def test_execute_tool_run_command_allow_skips_confirm_for_normal_cmd(isolated_perms):
    """Non-root commands under policy=allow must NOT prompt — preserves the
    pre-existing UX where shell calls flow through unattended.
    """
    from openagentic.cli import permissions as perm, tools

    cfg = perm._build_default()
    cfg.tools["run_command"].policy = "allow"
    perm.save(cfg)

    confirm_called = {"n": 0}

    async def confirm_fn(title, detail):
        confirm_called["n"] += 1
        return True

    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = SimpleNamespace(stdout="ok", stderr="", returncode=0)
        result = asyncio.run(tools.execute_tool(
            "run_command", {"command": "echo hi"}, confirm_fn=confirm_fn,
        ))
    assert confirm_called["n"] == 0
    assert "ok" in result


def test_execute_tool_allow_path_skips_confirm(tmp_path, isolated_perms):
    """A whitelisted path must not invoke confirm_fn at all — that's the point."""
    from openagentic.cli import permissions as perm, tools
    cfg = perm._build_default()
    cfg.tools["write_file"].allow_paths = [str(tmp_path)]
    perm.save(cfg)
    f = tmp_path / "ok.txt"

    confirm_called = {"n": 0}

    async def confirm_fn(title, detail):
        confirm_called["n"] += 1
        return True

    result = asyncio.run(tools.execute_tool(
        "write_file",
        {"path": str(f), "content": "hello"},
        confirm_fn=confirm_fn,
    ))
    assert result.startswith("OK:")
    assert f.read_text(encoding="utf-8") == "hello"
    assert confirm_called["n"] == 0
