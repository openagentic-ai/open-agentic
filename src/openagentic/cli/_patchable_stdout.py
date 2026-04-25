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
_patchable_stdout = _PatchableStdout()
