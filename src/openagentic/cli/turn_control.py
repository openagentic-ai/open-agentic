"""Turn-scoped steering and durable transcript checkpoints."""

from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from openagentic.runtime.extensions import Extensions


@dataclass
class TurnControl:
    steering: deque[str] = field(default_factory=deque)
    checkpoint: Callable[[list[dict]], None] | None = None
    extensions: "Extensions | None" = None
    event_sink: Callable | None = None
    codemode: bool = False

    def save(self, messages: list[dict]) -> None:
        if self.checkpoint:
            self.checkpoint(messages)

    def deliver(self, messages: list[dict]) -> bool:
        delivered = bool(self.steering)
        while self.steering:
            messages.append({"role": "user", "content": self.steering.popleft()})
        self.save(messages)
        return delivered

    async def notify(self, event: str, **data):
        if self.event_sink:
            from openagentic.runtime.extensions import invoke
            await invoke(self.event_sink, event, **data)


turn_control: ContextVar[TurnControl | None] = ContextVar("turn_control", default=None)


def pending_tool_calls(messages: list[dict]) -> set[str]:
    pending: set[str] = set()
    for message in messages:
        if message.get("role") == "assistant":
            pending.update(tc["id"] for tc in message.get("tool_calls", []) or [] if tc.get("id"))
        elif message.get("role") == "tool":
            pending.discard(message.get("tool_call_id"))
    return pending


def finish_interrupted_tools(messages: list[dict], reason: str) -> None:
    # Preserve completed effects; never rerun a tool to repair its transcript.
    for tool_id in sorted(pending_tool_calls(messages)):
        messages.append({"role": "tool", "tool_call_id": tool_id, "content": reason})
