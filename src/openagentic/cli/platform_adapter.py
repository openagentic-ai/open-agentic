"""OS-specific adapters for CLI runtime behavior.

This module exports a single ``CLI_PLATFORM`` instance whose concrete type
is selected at import time based on ``os.name``.  All call-sites should
import only ``CLI_PLATFORM`` (or ``CliPlatformBase`` for type hints).

Platform implementations live in sibling modules:
- ``_platform_posix.py``  — Linux / macOS / BSDs
- ``_platform_windows.py`` — Windows
"""

from __future__ import annotations

import os

from openagentic.cli._platform_base import CliPlatformBase

__all__ = ["CLI_PLATFORM", "CliPlatformBase"]


def _create_platform() -> CliPlatformBase:
    if os.name == "nt":
        from openagentic.cli._platform_windows import WindowsCliPlatform

        return WindowsCliPlatform()

    from openagentic.cli._platform_posix import PosixCliPlatform

    return PosixCliPlatform()


CLI_PLATFORM = _create_platform()
