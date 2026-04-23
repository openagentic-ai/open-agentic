"""OS-specific adapters for CLI runtime behavior."""

from __future__ import annotations

import asyncio
import os
import select
import sys
from pathlib import Path


class CliPlatformAdapter:
    """Encapsulates OS-specific behavior used by the CLI layer."""

    def __init__(self) -> None:
        self.is_windows = os.name == "nt"
        self._esc_pending = False
        self._esc_buffer = ""
        self._initial_termios: list | None = None
        if not self.is_windows:
            try:
                import termios

                if sys.stdin.isatty():
                    self._initial_termios = termios.tcgetattr(sys.stdin.fileno())
            except Exception:
                self._initial_termios = None

    def configure_event_loop_policy(self) -> None:
        """Avoid noisy Proactor shutdown callbacks on Windows CLI exit."""
        if not self.is_windows:
            return
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            # Keep default policy if selector policy is unavailable.
            return

    def secure_file_permissions(self, path: Path) -> None:
        """Restrict session file perms when the platform supports chmod semantics."""
        if self.is_windows:
            return
        try:
            os.chmod(path, 0o600)
        except OSError:
            return

    def should_skip_auto_editable_install(self) -> bool:
        """Windows launcher replacement is fragile; skip in-process editable reinstall."""
        return self.is_windows

    def clear_screen(self) -> None:
        if self.is_windows:
            os.system("cls")
            return
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def read_nav_key(self) -> str:
        if self.is_windows:
            import msvcrt

            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                return "enter"
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                if ch2 == "H":
                    return "up"
                if ch2 == "P":
                    return "down"
                return "other"
            if ch == "\x03":
                return "interrupt"
            if ch in ("q", "Q"):
                return "quit"
            return "other"

        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            self._debug_key(f"first={ch!r}")
            if self._esc_pending:
                # If a pending escape sequence is incomplete, do not swallow
                # a subsequent Enter/quit/interrupt key.
                if ch in ("\r", "\n"):
                    self._esc_pending = False
                    self._esc_buffer = ""
                    return "enter"
                if ch == "\x03":
                    self._esc_pending = False
                    self._esc_buffer = ""
                    return "interrupt"
                if ch in ("q", "Q"):
                    self._esc_pending = False
                    self._esc_buffer = ""
                    return "quit"
                self._esc_buffer += ch
                self._debug_key(f"pending_esc_buffer={self._esc_buffer!r}")
                if self._esc_buffer in {"[", "O", "[["}:
                    return "other"
                # Some terminals emit keypad Enter as ESC O M.
                if self._esc_buffer in {"OM", "[M"}:
                    self._esc_pending = False
                    self._esc_buffer = ""
                    return "enter"
                if self._esc_buffer in {"[A", "OA", "[[A"}:
                    self._esc_pending = False
                    self._esc_buffer = ""
                    return "up"
                if self._esc_buffer in {"[B", "OB", "[[B"}:
                    self._esc_pending = False
                    self._esc_buffer = ""
                    return "down"
                self._esc_pending = False
                self._esc_buffer = ""
                return "other"
            if ch in ("\r", "\n"):
                return "enter"
            if ch == "\x03":
                return "interrupt"
            # Some terminals / wrappers may transform arrow keys into caret notation.
            if ch == "^":
                c1 = self._read_char_with_timeout(0.12)
                c2 = self._read_char_with_timeout(0.12)
                c3 = self._read_char_with_timeout(0.12)
                seq = f"{c1}{c2}{c3}"
                self._debug_key(f"caret_seq={seq!r}")
                if seq in {"[[A", "[A", "OA"}:
                    return "up"
                if seq in {"[[B", "[B", "OB"}:
                    return "down"
                return "other"
            if ch == "\x1b":
                self._esc_pending = True
                self._esc_buffer = ""
                return "other"
            if ch in ("k", "K"):
                return "up"
            if ch in ("j", "J"):
                return "down"
            if ch in ("q", "Q"):
                return "quit"
            return "other"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    @staticmethod
    def _read_char_with_timeout(timeout_s: float) -> str:
        if not select.select([sys.stdin], [], [], timeout_s)[0]:
            return ""
        return sys.stdin.read(1)

    @staticmethod
    def _debug_key(message: str) -> None:
        if os.getenv("OPENAGENTIC_DEBUG_KEYS"):
            sys.stderr.write(f"[key-debug] {message}\n")
            sys.stderr.flush()

    def drain_stdin_buffer(self, settle_ms: int = 0) -> None:
        """Clear pending terminal input bytes to avoid key-sequence leaks.

        Args:
            settle_ms: keep draining until stdin stays quiet for this duration.
        """
        if self.is_windows:
            try:
                import msvcrt
                import time

                quiet_deadline = None
                while True:
                    consumed = False
                    while msvcrt.kbhit():
                        msvcrt.getwch()
                        consumed = True
                    if settle_ms <= 0:
                        break
                    if consumed:
                        quiet_deadline = time.monotonic() + (settle_ms / 1000.0)
                    elif quiet_deadline is not None and time.monotonic() >= quiet_deadline:
                        break
                    else:
                        # tiny sleep to wait for fragmented key bytes.
                        time.sleep(0.01)
            except Exception:
                return
            return

        try:
            import time

            quiet_deadline = None
            while True:
                consumed = False
                while select.select([sys.stdin], [], [], 0.0)[0]:
                    sys.stdin.read(1)
                    consumed = True
                if settle_ms <= 0:
                    break
                if consumed:
                    quiet_deadline = time.monotonic() + (settle_ms / 1000.0)
                elif quiet_deadline is not None and time.monotonic() >= quiet_deadline:
                    break
                else:
                    time.sleep(0.01)
        except Exception:
            return

    def ensure_line_input_mode(self) -> None:
        """Force terminal back to cooked mode for normal `input()` editing."""
        self._esc_pending = False
        self._esc_buffer = ""
        if self.is_windows:
            return
        if not sys.stdin.isatty():
            return
        try:
            import termios

            fd = sys.stdin.fileno()
            if self._initial_termios is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, self._initial_termios)
                return
            # Fallback: best-effort cooked mode if initial snapshot is unavailable.
            attrs = termios.tcgetattr(fd)
            attrs[0] |= termios.ICRNL | termios.IXON
            attrs[1] |= termios.OPOST
            attrs[3] |= termios.ICANON | termios.ECHO | termios.ECHOE | termios.ECHOK | termios.ISIG | termios.IEXTEN
            termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        except Exception:
            return


CLI_PLATFORM = CliPlatformAdapter()
