"""Windows CLI platform adapter."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from openagentic.cli._platform_base import CliPlatformBase


class WindowsCliPlatform(CliPlatformBase):
    """Terminal handling for Windows (cmd / PowerShell / Windows Terminal)."""

    # -- lifecycle -----------------------------------------------------------

    def configure_event_loop_policy(self) -> None:
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            return

    # -- filesystem ----------------------------------------------------------

    def secure_file_permissions(self, path: Path) -> None:
        # Windows does not support POSIX chmod semantics.
        return

    def should_skip_auto_editable_install(self) -> bool:
        return True

    # -- terminal: screen ----------------------------------------------------

    def clear_screen(self) -> None:
        import os

        os.system("cls")

    # -- terminal: key reading -----------------------------------------------

    def read_nav_key(self) -> str:
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

    # -- terminal: drain / restore -------------------------------------------

    def drain_stdin_buffer(self, settle_ms: int = 0) -> None:
        try:
            import msvcrt

            deadline = time.monotonic() + (settle_ms / 1000.0)
            while True:
                consumed = False
                while msvcrt.kbhit():
                    msvcrt.getwch()
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
        # Windows console does not need explicit mode restoration.
        return
