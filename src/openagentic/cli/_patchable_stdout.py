"""A file-like object that always delegates to the *current* ``sys.stdout``.

Rich ``Console`` captures ``sys.stdout`` at import time (module level).
When ``prompt_toolkit.patch_stdout()`` later replaces ``sys.stdout`` with
a proxy, Rich keeps writing to the *original* fd, causing ANSI escape codes
to bypass prompt_toolkit's terminal management and appear garbled.

``_patchable_stdout()`` fixes this by resolving ``sys.stdout`` on every
``write``/``flush`` call.  It also reports ``isatty() -> False`` so Rich
disables ANSI colour codes — only Unicode formatting (Panel, Rule,
Markdown) survives, which is safe under ``patch_stdout``.
"""

from __future__ import annotations

import sys
from typing import IO, cast


class _PatchableStdout:
    """File-like that delegates to whatever ``sys.stdout`` currently is."""

    def write(self, data: str) -> int:
        return sys.stdout.write(data)

    def flush(self) -> None:
        sys.stdout.flush()

    def isatty(self) -> bool:
        # Return False so Rich thinks it's writing to a pipe and skips ANSI
        # colour codes.  Structural rendering (Panel, Markdown, Rule) uses
        # Unicode and stays intact.
        return False

    @property
    def encoding(self) -> str:
        return getattr(sys.stdout, "encoding", "utf-8")

    @property
    def errors(self) -> str:
        return getattr(sys.stdout, "errors", "strict")


# Singleton — every Console instance shares the same delegating wrapper.
# Rich 的 Console 要求 file 是 IO[str]；本类只实现写侧
# （write/flush/isatty/encoding/errors），刻意不实现 read/seek，
# 这里按写侧契约声明，运行时行为不变。
_patchable_stdout: IO[str] = cast("IO[str]", _PatchableStdout())
