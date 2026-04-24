"""模块说明（中文）：`src/openagentic/cli/_platform_base.py`。\n\n该文件定义 ORM 基类与通用模型混入。\n"""

from __future__ import annotations

import abc
import os
import sys
from pathlib import Path


class CliPlatformBase(abc.ABC):
    """Interface that every platform adapter must implement.

    Callers interact with this via the ``CLI_PLATFORM`` singleton exported
    from ``platform_adapter.py``.  Each public method has a single, clear
    responsibility; OS-specific helpers stay private in the concrete class.
    """

    # -- lifecycle -----------------------------------------------------------

    @abc.abstractmethod
    def configure_event_loop_policy(self) -> None:
        """Adjust the asyncio event-loop policy for this platform."""

    # -- filesystem ----------------------------------------------------------

    def secure_file_permissions(self, path: Path) -> None:
        """Restrict *path* to owner-only access (``0o600``)."""
        try:
            os.chmod(path, 0o600)
        except OSError:
            return

    def should_skip_auto_editable_install(self) -> bool:
        """Return ``True`` when in-process ``pip install -e .`` is unsafe."""
        return False

    # -- terminal ------------------------------------------------------------

    @abc.abstractmethod
    def clear_screen(self) -> None:
        """Clear the terminal."""

    @abc.abstractmethod
    def read_nav_key(self) -> str:
        """Block until one navigation key is pressed.

        Returns one of: ``"up"``, ``"down"``, ``"enter"``, ``"quit"``,
        ``"interrupt"``, ``"other"``.
        """

    @abc.abstractmethod
    def drain_stdin_buffer(self, settle_ms: int = 0) -> None:
        """Discard pending input bytes.

        When *settle_ms* > 0 keep draining until stdin stays quiet for that
        many milliseconds.
        """

    @abc.abstractmethod
    def ensure_line_input_mode(self) -> None:
        """Restore the terminal to cooked / line-editing mode."""

    # -- shared helpers (not abstract) ---------------------------------------

    @staticmethod
    def _debug_key(message: str) -> None:
        if os.getenv("OPENAGENTIC_DEBUG_KEYS"):
            sys.stderr.write(f"[key-debug] {message}\n")
            sys.stderr.flush()
