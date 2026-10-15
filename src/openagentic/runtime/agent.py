"""Embeddable Python session using the CLI's ReAct loop and tool permissions."""

import asyncio
import io
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import IO, cast

from openagentic.cli.sessions import SessionStore, TEXT as SESSION_TEXT
from openagentic.cli.turn_control import TurnControl, turn_control, finish_interrupted_tools
from openagentic.runtime.extensions import Extensions, TEXT
from openagentic.cli._patchable_stdout import output_stream


class _SilentOutput(io.TextIOBase):
    def write(self, text):
        return len(text)


class AgentSession:
    def __init__(self, *, model: str, api_base=None, api_key=None, system_prompt=None,
                 session_dir: Path | None = None, cwd: Path | None = None, resume=None,
                 extensions: Extensions | None = None, confirm_fn=None, on_event=None,
                 codemode=False, output=None):
        self.model, self.api_base, self.api_key = model, api_base, api_key
        self.extensions = extensions or Extensions()
        self.confirm_fn, self.on_event = confirm_fn, on_event
        self.output = output if output is not None else _SilentOutput()
        self.store = SessionStore(session_dir, cwd)
        if resume:
            self.messages = self.store.resume(None if resume == "latest" else resume)
            finish_interrupted_tools(self.messages, SESSION_TEXT["interrupted"])
        else:
            self.store.create()
            self.messages = [{"role": "system", "content": system_prompt or TEXT["system"]}]
        self.store.save(self.messages)
        self.control = TurnControl(checkpoint=self.store.save, extensions=self.extensions, event_sink=self.emit)
        self._followups: deque[str] = deque()
        self._task: asyncio.Task | None = None
        self._started = False
        self._closed = False
        self._codemode = codemode

    @property
    def id(self):
        return self.store.id

    @property
    def busy(self):
        return self._task is not None

    def _check_open(self):
        if self._closed:
            raise RuntimeError(TEXT["closed"])

    async def emit(self, event, **data):
        from openagentic.runtime.extensions import invoke
        payload = {"session_id": self.id, **data}
        await self.extensions.emit(event, payload)
        if self.on_event:
            await invoke(self.on_event, {"type": event, **payload})

    async def start(self):
        self._check_open()
        if not self._started:
            await self.emit("session_start")
            self._started = True

    def steer(self, text: str):
        self._check_open()
        if not self.busy:
            raise RuntimeError(TEXT["no_active_run"])
        self.control.steering.append(text)

    def follow_up(self, text: str):
        self._check_open()
        if not self.busy:
            raise RuntimeError(TEXT["no_active_run"])
        self._followups.append(text)

    def cancel(self):
        if self._task:
            self._task.cancel()

    async def _confirm(self, title, detail):
        from openagentic.runtime.extensions import invoke
        return bool(await invoke(self.confirm_fn, title, detail)) if self.confirm_fn else False

    async def prompt(self, text: str) -> str:
        from openagentic.cli.react import react_loop
        from openagentic.cli.tools import TOOLS
        self._check_open()
        if not isinstance(text, str) or not text.strip():
            raise ValueError(TEXT["prompt_type"])
        if self.busy:
            raise RuntimeError(TEXT["busy"])
        self._task = asyncio.current_task()
        token = turn_control.set(self.control)
        output_token = output_stream.set(cast(IO[str], self.output))
        try:
            await self.start()
            while True:
                await self.emit("agent_start", prompt=text)
                tools = [*TOOLS, *self.extensions.schemas()]
                if self._codemode:
                    from openagentic.runtime.codemode import tool_schema
                    tools.append(tool_schema())
                    self.control.codemode = True
                result = await react_loop(text, self.messages, self.model, self.api_base,
                                          self.api_key, confirm_fn=self._confirm, tools=tools)
                self.store.save(self.messages)
                await self.emit("agent_end", result=result)
                if not self._followups:
                    return result
                text = self._followups.popleft()
        finally:
            try:
                finish_interrupted_tools(self.messages, SESSION_TEXT["interrupted"])
                self.store.save(self.messages)
                # Preserve queued user input after an interrupted run for the next prompt.
                while self.control.steering:
                    self._followups.appendleft(self.control.steering.pop())
            finally:
                turn_control.reset(token)
                output_stream.reset(output_token)
                self._task = None

    async def execute_tool(self, name: str, args: dict) -> str:
        self._check_open()
        if name == "codemode" and self._codemode:
            from openagentic.runtime.codemode import run_script
            from openagentic.cli.tools import TOOLS
            names = [t["function"]["name"] for t in TOOLS] + list(self.extensions.tools)
            return await run_script(args["code"], self.execute_tool, tool_names=names)
        return await self.extensions.execute(name, args, confirm_fn=self._confirm)

    async def command(self, name: str, args: str):
        from openagentic.runtime.extensions import invoke
        self._check_open()
        await self.start()
        if name not in self.extensions.commands:
            raise ValueError(TEXT["unknown_command"].format(name=name))
        return await invoke(self.extensions.commands[name], args)

    def tree(self):
        return self.store.tree()

    def checkout(self, node: int):
        if self.busy:
            raise RuntimeError(TEXT["busy"])
        self.messages = self.store.checkout(node)
        return deepcopy(self.messages)

    async def close(self):
        if self._closed:
            return
        task = self._task
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        try:
            if self._started:
                await self.emit("session_shutdown")
        finally:
            self._closed = True
            self.store.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()
