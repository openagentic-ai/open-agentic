"""Test encoding fixes for CLI tools, bootstrap fingerprint, and sequential repl."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock



# ============================================================================
# cli/tools.py — subprocess / file encoding
# ============================================================================

def test_run_command_sync_passes_utf8_encoding_to_subprocess():
    """_run_command_sync must pass encoding='utf-8' to subprocess.run."""
    from openagentic.cli import tools

    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = SimpleNamespace(
            stdout="hello \u4e2d\u6587", stderr="", returncode=0,
        )
        result = tools._run_command_sync("echo test")
        assert "hello \u4e2d\u6587" in result
        _, kwargs = m_run.call_args
        assert kwargs.get("encoding") == "utf-8", (
            f"subprocess.run must receive encoding='utf-8', got: {kwargs}"
        )


def test_read_file_sync_uses_utf8_encoding():
    """_read_file_sync must open files with encoding='utf-8'."""
    from openagentic.cli import tools

    with mock.patch("builtins.open", mock.mock_open(read_data="中文内容")) as m_open:
        result = tools._read_file_sync("/fake/path.txt")
        assert "中文内容" in result
        m_open.assert_called_once_with("/fake/path.txt", encoding="utf-8")


def test_run_command_sync_truncates_long_output():
    """Output longer than MAX_OUTPUT (4000) must be truncated."""
    from openagentic.cli import tools

    long_text = "x" * 5000
    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = SimpleNamespace(
            stdout=long_text, stderr="", returncode=0,
        )
        result = tools._run_command_sync("cat large_file")
        assert len(result) <= 4000 + 50
        assert "... (truncated" in result


def test_run_command_sync_includes_stderr():
    from openagentic.cli import tools

    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = SimpleNamespace(
            stdout="ok", stderr="err msg", returncode=0,
        )
        result = tools._run_command_sync("cmd")
        assert "ok" in result
        assert "err msg" in result


def test_run_command_sync_empty_output():
    from openagentic.cli import tools

    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = SimpleNamespace(
            stdout="", stderr="", returncode=0,
        )
        result = tools._run_command_sync("cmd")
        assert result == "(no output)"


def test_run_command_sync_nonzero_exit_code():
    from openagentic.cli import tools

    with mock.patch("subprocess.run") as m_run:
        m_run.return_value = SimpleNamespace(
            stdout="failed", stderr="", returncode=1,
        )
        result = tools._run_command_sync("bad cmd")
        assert "[exit code 1]" in result


# ============================================================================
# cli/bootstrap.py — fingerprint only tracks pyproject.toml
# ============================================================================

class TestBuildSourceFingerprint:
    """_build_source_fingerprint must only depend on pyproject.toml,
    NOT on any .py files under src/."""

    def test_fingerprint_depends_on_pyproject(self, tmp_path: Path):
        from openagentic.cli.bootstrap import _build_source_fingerprint

        pyproject = tmp_path / "pyproject.toml"
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        pyproject.write_text("[project]\nname = 'test'", encoding="utf-8")
        fp1 = _build_source_fingerprint(pyproject, src_dir)

        pyproject.write_text("[project]\nname = 'different'", encoding="utf-8")
        fp2 = _build_source_fingerprint(pyproject, src_dir)

        assert fp1 != fp2, "Fingerprint must change when pyproject.toml changes"

    def test_fingerprint_ignores_py_files(self, tmp_path: Path):
        from openagentic.cli.bootstrap import _build_source_fingerprint

        pyproject = tmp_path / "pyproject.toml"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        pyproject.write_text("[project]\nname = 'test'", encoding="utf-8")

        fp1 = _build_source_fingerprint(pyproject, src_dir)

        (src_dir / "main.py").write_text("print('hello')", encoding="utf-8")
        fp2 = _build_source_fingerprint(pyproject, src_dir)

        assert fp1 == fp2, (
            "Fingerprint must NOT change when .py files added"
        )

    def test_fingerprint_ignores_py_file_modifications(self, tmp_path: Path):
        from openagentic.cli.bootstrap import _build_source_fingerprint

        pyproject = tmp_path / "pyproject.toml"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        pyproject.write_text("[project]\nname = 'test'", encoding="utf-8")
        (src_dir / "module.py").write_text("v1", encoding="utf-8")

        fp1 = _build_source_fingerprint(pyproject, src_dir)

        (src_dir / "module.py").write_text("v2 completely different", encoding="utf-8")
        fp2 = _build_source_fingerprint(pyproject, src_dir)

        assert fp1 == fp2, "Fingerprint must NOT change when .py files are modified"

    def test_fingerprint_ignores_py_file_deletions(self, tmp_path: Path):
        from openagentic.cli.bootstrap import _build_source_fingerprint

        pyproject = tmp_path / "pyproject.toml"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        pyproject.write_text("[project]\nname = 'test'", encoding="utf-8")
        py_file = src_dir / "temp.py"
        py_file.write_text("temporary", encoding="utf-8")

        fp1 = _build_source_fingerprint(pyproject, src_dir)

        py_file.unlink()
        fp2 = _build_source_fingerprint(pyproject, src_dir)

        assert fp1 == fp2, "Fingerprint must NOT change when .py files are deleted"

    def test_fingerprint_returns_empty_when_no_pyproject(self, tmp_path: Path):
        from openagentic.cli.bootstrap import _build_source_fingerprint

        pyproject = tmp_path / "nonexistent.toml"
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        result = _build_source_fingerprint(pyproject, src_dir)
        assert result == ""


def test_bootstrap_subprocess_passes_utf8_encoding():
    """maybe_auto_install_editable must pass encoding='utf-8' to subprocess.run."""
    from openagentic.cli import bootstrap

    src = Path(bootstrap.__file__).read_text(encoding="utf-8")
    assert 'encoding="utf-8"' in src, (
        "bootstrap.py subprocess.run must include encoding='utf-8'"
    )


# ============================================================================
# cli/react.py — no raw ANSI, no Live spinner
# ============================================================================

def test_react_no_raw_ansi_in_source():
    """react.py must not contain raw \\033 ANSI escape sequences."""
    src = _read_src("openagentic", "cli", "react.py")
    assert "\\033" not in src, (
        "react.py must not use raw \\033 ANSI escapes"
    )
    assert 'print(f"\\n\\033[33m' not in src


def test_react_no_live_spinner_in_source():
    """react.py must not import Live or Spinner — uses \r-based spinner instead."""
    src = _read_src("openagentic", "cli", "react.py")
    assert "from rich.live import Live" not in src
    assert "from rich.spinner import Spinner" not in src


def test_react_has_cr_spinner():
    """react.py must have _spin_while with braille spinner and \\r."""
    src = _read_src("openagentic", "cli", "react.py")
    assert "_spin_while" in src, "must define _spin_while"
    assert "_SPINNER" in src, "must have braille spinner frames"
    assert "sys.stdout.write" in src, "must write spinner directly to stdout"
    assert "asyncio.create_task" in src, "spinner must run as concurrent task"


# ============================================================================
# cli/repl.py — sequential loop (no concurrent producer/consumer)
# ============================================================================

def test_repl_has_concurrent_producer_consumer():
    """repl.py must use Producer-Consumer pattern for Ctrl+C interrupt support (P1-1)."""
    src = _read_src("openagentic", "cli", "repl.py")
    assert "_input_producer" in src, (
        "repl.py must have _input_producer for concurrent input handling"
    )
    assert "_execution_consumer" in src, (
        "repl.py must have _execution_consumer for sequential command processing"
    )
    assert "asyncio.Queue" in src, (
        "repl.py must use asyncio.Queue for producer-consumer communication"
    )


def test_repl_has_sequential_main_loop():
    """main_loop must keep its prompt → process backbone wired up.

    react_loop now lives behind _run_react_turn in slash_commands.py after
    the refactor; repl.py invokes that helper instead of importing react_loop
    directly.
    """
    repl_src = _read_src("openagentic", "cli", "repl.py")
    assert "while True:" in repl_src
    assert "session.prompt_async" in repl_src
    assert "_run_react_turn" in repl_src, (
        "repl.py must dispatch user turns through _run_react_turn"
    )
    slash_src = _read_src("openagentic", "cli", "slash_commands.py")
    assert "react_loop(" in slash_src, (
        "slash_commands.py must invoke react_loop inside _run_react_turn"
    )


def test_input_prompt_has_top_separator():
    """The prompt must include full-width top border in round style: ╭...╮.

    UI primitives moved into slash_commands.py during the repl.py refactor.
    """
    src = _read_src("openagentic", "cli", "slash_commands.py")
    assert "╭" in src, "must have top-left corner ╭"
    assert "╮" in src, "must have top-right corner ╮"


def test_input_prompt_has_bottom_separator():
    """The bottom_toolbar must include full-width bottom border: ╰...╯."""
    src = _read_src("openagentic", "cli", "slash_commands.py")
    assert "╰" in src, "must have bottom-left corner ╰"
    assert "╯" in src, "must have bottom-right corner ╯"
    assert "shutil.get_terminal_size" in src, "must dynamically compute width"


def test_bottom_toolbar_has_hints():
    """The bottom_toolbar must include hint text below the separator."""
    src = _read_src("openagentic", "cli", "slash_commands.py")
    assert "SLASH_COMMANDS" in src, "must have slash command list"
    assert "/help" in src, "slash commands must include /help"
    assert "/quit" in src, "slash commands must include /quit"
    assert "get_app" in src, "must access current buffer for live filtering"


# ============================================================================
# agent/tools.py — encoding in subprocess / file I/O
# ============================================================================

def test_agent_run_command_uses_utf8_decode():
    """_run_command must decode stdout with 'utf-8'."""
    src = _read_src("openagentic", "agent", "tools.py")
    assert 'decode("utf-8", errors="replace")' in src


def test_agent_python_exec_uses_utf8_decode():
    """_python_exec must decode stdout with 'utf-8'."""
    src = _read_src("openagentic", "agent", "tools.py")
    assert src.count('decode("utf-8", errors="replace")') >= 2


def test_agent_read_file_uses_utf8_encoding():
    """_read_file must open files with encoding='utf-8'."""
    src = _read_src("openagentic", "agent", "tools.py")
    assert 'encoding="utf-8"' in src


# ============================================================================
# Dockerfile — locale/env vars for UTF-8
# ============================================================================

def test_dockerfile_has_utf8_locale():
    """Dockerfile must set PYTHONIOENCODING and LANG for UTF-8."""
    df = (Path(__file__).resolve().parents[2] / "Dockerfile"
           ).read_text(encoding="utf-8")
    assert "PYTHONIOENCODING=utf-8" in df
    assert "PYTHONUTF8=1" in df
    assert "LANG=C.UTF-8" in df


# ============================================================================
# helpers
# ============================================================================

def _read_src(*parts: str) -> str:
    root = Path(__file__).resolve().parents[2] / "src"
    return (root.joinpath(*parts)).read_text(encoding="utf-8")
