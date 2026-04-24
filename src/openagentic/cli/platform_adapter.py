"""模块说明（中文）：`src/openagentic/cli/platform_adapter.py`。\n\n该文件属于 CLI 子系统，处理终端交互、命令解析或平台适配。\n"""

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
