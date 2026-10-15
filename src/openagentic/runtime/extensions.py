"""Explicit, trusted Python extensions for tools and agent lifecycle hooks."""

from copy import deepcopy
import importlib.util
import inspect
import json
from pathlib import Path
import re
import uuid

from jsonschema import validate

TEXT = json.loads(Path(__file__).with_name("messages.json").read_text(encoding="utf-8"))


async def invoke(callback, *args, **kwargs):
    result = callback(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


class Extensions:
    def __init__(self) -> None:
        self.tools: dict = {}
        self.hooks: dict = {}
        self.commands: dict = {}
        self.providers: dict = {}
        self.statuses: dict = {}

    def register_tool(self, name, description, parameters, handler, *, read_only=False):
        from openagentic.cli.tools import TOOLS
        reserved = {t["function"]["name"] for t in TOOLS} | {"codemode"}
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in reserved or name in self.tools:
            raise ValueError(TEXT["invalid_tool"].format(name=name))
        self.tools[name] = {"schema": {"type": "function", "function": {
            "name": name, "description": description, "parameters": parameters,
        }}, "handler": handler, "read_only": read_only}

    def on(self, event, handler):
        self.hooks.setdefault(event, []).append(handler)

    def register_command(self, name, handler):
        from openagentic.cli.slash_commands import SLASH_COMMANDS
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name) or "/" + name in SLASH_COMMANDS or name in self.commands:
            raise ValueError(TEXT["invalid_command"].format(name=name))
        self.commands[name] = handler

    def register_provider(self, name, handler):
        if name in self.providers:
            raise ValueError(TEXT["duplicate_provider"].format(name=name))
        self.providers[name] = handler

    def register_status(self, name, render):
        self.statuses[name] = render

    def status(self):
        return " · ".join(str(render()) for render in self.statuses.values())

    def load(self, paths):
        # Never discover executable code from the current project implicitly.
        for path in paths:
            path = Path(path).expanduser().resolve()
            spec = importlib.util.spec_from_file_location("openagentic_extension_" + uuid.uuid4().hex, path)
            if spec is None or spec.loader is None:
                raise ValueError(TEXT["load_error"].format(path=path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.setup(self)

    async def emit(self, event, data):
        for handler in self.hooks.get(event, []):
            changed = await invoke(handler, data)
            if changed is not None:
                data = changed
        return data

    async def complete(self, messages, model, fallback, **kwargs):
        context = await self.emit("context", deepcopy(messages))
        provider = model.partition("/")[0]
        return await invoke(self.providers.get(provider, fallback), context, model, **kwargs)

    def schemas(self, *, plan_mode=False):
        return [tool["schema"] for tool in self.tools.values() if not plan_mode or tool["read_only"]]

    async def execute(self, name, args, *, confirm_fn=None, plan_mode=False, builtin=None):
        from openagentic.cli.tools import TOOLS, execute_tool, filter_tools_for_plan_mode
        call = await self.emit("tool_call", {"name": name, "arguments": deepcopy(args)})
        if call.get("blocked"):
            return TEXT["blocked"].format(reason=call["blocked"])
        name, args = call["name"], call["arguments"]
        try:
            if name in self.tools:
                tool = self.tools[name]
                if plan_mode and not tool["read_only"]:
                    return TEXT["plan_refused"]
                validate(args, tool["schema"]["function"]["parameters"])
                # Extension code has host privileges; every custom operation is opt-in.
                if confirm_fn is None or not await confirm_fn(TEXT["custom_confirm"].format(name=name), json.dumps(args, ensure_ascii=False)):
                    return TEXT["custom_refused"]
                result = await invoke(tool["handler"], args)
                if not isinstance(result, str):
                    result = json.dumps(result, ensure_ascii=False)
            else:
                allowed = filter_tools_for_plan_mode(TOOLS) if plan_mode else TOOLS
                if name not in {t["function"]["name"] for t in allowed}:
                    return TEXT["error"].format(error=TEXT["unknown_tool"].format(name=name))
                result = await (builtin or execute_tool)(name, args, confirm_fn=confirm_fn)
        except Exception as exc:
            return TEXT["error"].format(error=str(exc))
        transformed = await self.emit("tool_result", {**call, "result": result})
        return str(transformed["result"])
