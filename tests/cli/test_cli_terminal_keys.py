"""Unit tests for CLI terminal key parsing behavior."""

from __future__ import annotations

from collections import deque

from openagentic.cli.platform_adapter import CliPlatformAdapter


class _FakeStdin:
    def __init__(self, chars: list[str]):
        self._chars = deque(chars)

    def fileno(self) -> int:
        return 0

    def isatty(self) -> bool:
        return True

    def read(self, _n: int) -> str:
        if not self._chars:
            return ""
        return self._chars.popleft()


def _patch_posix_raw_deps(monkeypatch, fake_stdin: _FakeStdin):
    import sys
    import termios
    import tty

    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(termios, "tcgetattr", lambda _fd: [0, 0, 0, 0, 0, 0, [0] * 32])
    monkeypatch.setattr(termios, "tcsetattr", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tty, "setraw", lambda _fd: None)


def test_read_nav_key_handles_fragmented_down_arrow(monkeypatch):
    """Down arrow split across reads should still be parsed as `down`."""
    adapter = CliPlatformAdapter()
    adapter.is_windows = False
    adapter._esc_pending = True
    adapter._esc_buffer = ""

    # First call gets '[', second call gets 'B' (fragmented ESC sequence).
    fake_stdin = _FakeStdin(["[", "B"])
    _patch_posix_raw_deps(monkeypatch, fake_stdin)

    first = adapter.read_nav_key()
    second = adapter.read_nav_key()

    assert first == "other"
    assert second == "down"
    assert adapter._esc_pending is False
    assert adapter._esc_buffer == ""


def test_read_nav_key_lonely_escape_sets_pending(monkeypatch):
    """A standalone ESC should mark parser pending for next fragment."""
    adapter = CliPlatformAdapter()
    adapter.is_windows = False

    fake_stdin = _FakeStdin(["\x1b"])
    _patch_posix_raw_deps(monkeypatch, fake_stdin)

    key = adapter.read_nav_key()
    assert key == "other"
    assert adapter._esc_pending is True


def test_read_nav_key_plain_chars_remain_other(monkeypatch):
    """Normal text input should not be mistaken as navigation keys."""
    adapter = CliPlatformAdapter()
    adapter.is_windows = False

    fake_stdin = _FakeStdin(["你"])
    _patch_posix_raw_deps(monkeypatch, fake_stdin)

    key = adapter.read_nav_key()
    assert key == "other"


def test_read_nav_key_handles_keypad_enter_sequence(monkeypatch):
    """Keypad Enter (ESC O M) should be parsed as enter."""
    adapter = CliPlatformAdapter()
    adapter.is_windows = False

    fake_stdin = _FakeStdin(["\x1b", "O", "M"])
    _patch_posix_raw_deps(monkeypatch, fake_stdin)

    first = adapter.read_nav_key()
    second = adapter.read_nav_key()
    third = adapter.read_nav_key()

    assert first == "other"
    assert second == "other"
    assert third == "enter"


def test_read_nav_key_pending_escape_does_not_swallow_enter(monkeypatch):
    """If ESC state is pending, next Enter should still confirm selection."""
    adapter = CliPlatformAdapter()
    adapter.is_windows = False
    adapter._esc_pending = True
    adapter._esc_buffer = ""

    fake_stdin = _FakeStdin(["\r"])
    _patch_posix_raw_deps(monkeypatch, fake_stdin)

    key = adapter.read_nav_key()
    assert key == "enter"
    assert adapter._esc_pending is False
    assert adapter._esc_buffer == ""
