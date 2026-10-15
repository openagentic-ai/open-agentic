"""Session-local activity state rendered exclusively by prompt_toolkit."""

from contextvars import ContextVar
from dataclasses import dataclass
import time

from prompt_toolkit.layout import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition


@dataclass
class ActivityStatus:
    text: str = ""

    def frame(self, tick: int | None = None) -> str:
        if not self.text:
            return ""
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        tick = int(time.monotonic() / 0.08) if tick is None else tick
        return f"  {frames[tick % len(frames)]} {self.text}"

    def container(self):
        return ConditionalContainer(
            Window(FormattedTextControl(self.frame), height=1),
            filter=Condition(lambda: bool(self.text)),
        )


activity_status: ContextVar[ActivityStatus | None] = ContextVar("activity_status", default=None)
