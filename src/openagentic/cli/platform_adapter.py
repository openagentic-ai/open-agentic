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
            if ch in ("\x1b", "q", "Q"):
                return "quit"
            return "other"

        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                return "enter"
            if ch == "\x03":
                return "interrupt"
            if ch == "\x1b":
                seq = ""
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    seq += sys.stdin.read(1)
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    seq += sys.stdin.read(1)
                if seq == "[A":
                    return "up"
                if seq == "[B":
                    return "down"
                return "quit"
            if ch in ("q", "Q"):
                return "quit"
            return "other"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


CLI_PLATFORM = CliPlatformAdapter()
