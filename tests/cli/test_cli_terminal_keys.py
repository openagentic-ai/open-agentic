"""Unit tests for CLI terminal key parsing behavior."""

from __future__ import annotations

from collections import deque

from openagentic.cli._platform_posix import PosixCliPlatform

FAKE_FD = 99


class _FakeStdin:
    """Minimal stdin stub that provides fileno() for termios calls."""

    def fileno(self) -> int:
        return FAKE_FD

    def isatty(self) -> bool:
        return True


def _make_adapter_with_bytes(monkeypatch, raw_bytes: bytes):
    """Create an adapter that reads from a byte sequence via os.read / select.select."""
    import sys
    import termios
    import tty

    adapter = PosixCliPlatform.__new__(PosixCliPlatform)
    adapter._initial_termios = None

    buf = deque(raw_bytes)

    monkeypatch.setattr(sys, "stdin", _FakeStdin())
    monkeypatch.setattr(termios, "tcgetattr", lambda _fd: [0, 0, 0, 0, 0, 0, [0] * 32])
    monkeypatch.setattr(termios, "tcsetattr", lambda *_a, **_k: None)
    monkeypatch.setattr(tty, "setraw", lambda _fd: None)

    import os as _os
    import select as _select

    _orig_os_read = _os.read

    def fake_os_read(fd, n):
        if fd == FAKE_FD and buf:
            return bytes([buf.popleft()])
        return _orig_os_read(fd, n)

    def fake_select(rlist, wlist, xlist, timeout=None):
        if rlist and FAKE_FD in rlist and buf:
            return rlist, wlist, xlist
        return [], wlist, xlist

    monkeypatch.setattr(_os, "read", fake_os_read)
    monkeypatch.setattr(_select, "select", fake_select)

    return adapter


def test_read_nav_key_down_arrow_single_call(monkeypatch):
    """Down arrow (ESC [ B) should be parsed in a single read_nav_key call."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b[B")
    assert adapter.read_nav_key() == "down"


def test_read_nav_key_up_arrow_single_call(monkeypatch):
    """Up arrow (ESC [ A) should be parsed in a single read_nav_key call."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b[A")
    assert adapter.read_nav_key() == "up"


def test_read_nav_key_lonely_escape_returns_other(monkeypatch):
    """A standalone ESC with no follow-up should return 'other'."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b")
    assert adapter.read_nav_key() == "other"


def test_read_nav_key_plain_chars_remain_other(monkeypatch):
    """Non-navigation ASCII chars should return 'other'."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"x")
    assert adapter.read_nav_key() == "other"


def test_read_nav_key_handles_keypad_enter_sequence(monkeypatch):
    """Keypad Enter (ESC O M) should be parsed as enter in a single call."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1bOM")
    assert adapter.read_nav_key() == "enter"


def test_read_nav_key_csi_enter_sequence(monkeypatch):
    """Keypad Enter variant (ESC [ M) should be parsed as enter."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b[M")
    assert adapter.read_nav_key() == "enter"


def test_read_nav_key_extended_escape_up(monkeypatch):
    """Extended escape (ESC [ [ A) should be parsed as up."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b[[A")
    assert adapter.read_nav_key() == "up"


def test_read_nav_key_extended_escape_down(monkeypatch):
    """Extended escape (ESC [ [ B) should be parsed as down."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b[[B")
    assert adapter.read_nav_key() == "down"


def test_read_nav_key_app_mode_up(monkeypatch):
    """Application mode up arrow (ESC O A) should be parsed as up."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1bOA")
    assert adapter.read_nav_key() == "up"


def test_read_nav_key_app_mode_down(monkeypatch):
    """Application mode down arrow (ESC O B) should be parsed as down."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1bOB")
    assert adapter.read_nav_key() == "down"


def test_read_nav_key_rapid_arrows_correct_count(monkeypatch):
    """Rapid consecutive down arrows should each be parsed correctly."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x1b[B\x1b[B")
    assert adapter.read_nav_key() == "down"
    assert adapter.read_nav_key() == "down"


def test_read_nav_key_enter(monkeypatch):
    """Enter key should be correctly identified."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\r")
    assert adapter.read_nav_key() == "enter"


def test_read_nav_key_vim_keys(monkeypatch):
    """j/k keys should map to down/up."""
    a1 = _make_adapter_with_bytes(monkeypatch, b"j")
    assert a1.read_nav_key() == "down"

    a2 = _make_adapter_with_bytes(monkeypatch, b"k")
    assert a2.read_nav_key() == "up"


def test_read_nav_key_quit(monkeypatch):
    """q key should return quit."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"q")
    assert adapter.read_nav_key() == "quit"


def test_read_nav_key_interrupt(monkeypatch):
    """Ctrl-C should return interrupt."""
    adapter = _make_adapter_with_bytes(monkeypatch, b"\x03")
    assert adapter.read_nav_key() == "interrupt"
