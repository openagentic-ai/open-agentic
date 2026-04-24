"""POSIX (Linux / macOS) CLI platform adapter."""

from __future__ import annotations

import os
import select
import sys

from openagentic.cli._platform_base import CliPlatformBase


class PosixCliPlatform(CliPlatformBase):
    """Terminal handling for POSIX systems (Linux, macOS, BSDs)."""

    def __init__(self) -> None:
        self._initial_termios: list | None = None
        try:
            import termios

            if sys.stdin.isatty():
                self._initial_termios = termios.tcgetattr(sys.stdin.fileno())
        except Exception:
            self._initial_termios = None

    # -- lifecycle -----------------------------------------------------------

    def configure_event_loop_policy(self) -> None:
        # POSIX default policy is fine.
        return

    # -- terminal: screen ----------------------------------------------------

    def clear_screen(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    # -- terminal: key reading -----------------------------------------------

    def read_nav_key(self) -> str:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = self._read_raw_char(fd)
            self._debug_key(f"first={ch!r}")
            if ch in ("\r", "\n"):
                return "enter"
            if ch == "\x03":
                return "interrupt"
            if ch == "\x1b":
                return self._parse_escape_sequence(fd)
            if ch == "^":
                return self._parse_caret_sequence(fd)
            if ch in ("k", "K"):
                return "up"
            if ch in ("j", "J"):
                return "down"
            if ch in ("q", "Q"):
                return "quit"
            return "other"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    # -- terminal: drain / restore -------------------------------------------

    def drain_stdin_buffer(self, settle_ms: int = 0) -> None:
        try:
            import time

            fd = sys.stdin.fileno()
            deadline = time.monotonic() + (settle_ms / 1000.0)
            while True:
                consumed = False
                while select.select([fd], [], [], 0.0)[0]:
                    os.read(fd, 1)
                    consumed = True
                if settle_ms <= 0:
                    break
                if consumed:
                    deadline = time.monotonic() + (settle_ms / 1000.0)
                elif time.monotonic() >= deadline:
                    break
                else:
                    time.sleep(0.01)
        except Exception:
            return

    def ensure_line_input_mode(self) -> None:
        if not sys.stdin.isatty():
            return
        try:
            import termios

            fd = sys.stdin.fileno()
            if self._initial_termios is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, self._initial_termios)
                return
            attrs = termios.tcgetattr(fd)
            attrs[0] |= termios.ICRNL | termios.IXON
            attrs[1] |= termios.OPOST
            attrs[3] |= (
                termios.ICANON
                | termios.ECHO
                | termios.ECHOE
                | termios.ECHOK
                | termios.ISIG
                | termios.IEXTEN
            )
            termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        except Exception:
            return

    # -- private helpers -----------------------------------------------------

    def _parse_escape_sequence(self, fd: int) -> str:
        """Read a complete ANSI escape sequence (raw mode must be active)."""
        c1 = self._read_raw_char_with_timeout(fd, 0.1)
        self._debug_key(f"esc_c1={c1!r}")
        if c1 == "":
            return "other"
        if c1 == "[":
            c2 = self._read_raw_char_with_timeout(fd, 0.1)
            self._debug_key(f"esc_c2={c2!r}")
            if c2 == "A":
                return "up"
            if c2 == "B":
                return "down"
            if c2 == "M":
                return "enter"
            if c2 == "[":
                c3 = self._read_raw_char_with_timeout(fd, 0.1)
                self._debug_key(f"esc_c3={c3!r}")
                if c3 == "A":
                    return "up"
                if c3 == "B":
                    return "down"
            return "other"
        if c1 == "O":
            c2 = self._read_raw_char_with_timeout(fd, 0.1)
            self._debug_key(f"esc_O_c2={c2!r}")
            if c2 == "A":
                return "up"
            if c2 == "B":
                return "down"
            if c2 == "M":
                return "enter"
            return "other"
        return "other"

    def _parse_caret_sequence(self, fd: int) -> str:
        """Handle caret-notation arrow keys (``^[[A`` etc.)."""
        c1 = self._read_raw_char_with_timeout(fd, 0.12)
        c2 = self._read_raw_char_with_timeout(fd, 0.12)
        c3 = self._read_raw_char_with_timeout(fd, 0.12)
        seq = f"{c1}{c2}{c3}"
        self._debug_key(f"caret_seq={seq!r}")
        if seq in {"[[A", "[A", "OA"}:
            return "up"
        if seq in {"[[B", "[B", "OB"}:
            return "down"
        return "other"

    @staticmethod
    def _read_raw_char(fd: int) -> str:
        return os.read(fd, 1).decode("latin-1")

    @staticmethod
    def _read_raw_char_with_timeout(fd: int, timeout_s: float) -> str:
        if not select.select([fd], [], [], timeout_s)[0]:
            return ""
        return os.read(fd, 1).decode("latin-1")
