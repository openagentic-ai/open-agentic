"""Opt-in JavaScript tool composition inside a WebAssembly runtime."""

import asyncio
import json

from openagentic.runtime.extensions import TEXT

MAX_CODE_BYTES = 128 * 1024
MAX_TOOL_RESULT_BYTES = 1024 * 1024
MAX_CALLS = 64
MAX_JS_SECONDS = 1.0
READ_TOOLS = {"read_file", "core_memory_search", "episodic_search", "procedural_search"}


def tool_schema():
    return {"type": "function", "function": {
        "name": "codemode", "description": TEXT["codemode_description"],
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    }}


async def run_script(code, execute, *, tool_names=None, read_only_tools=READ_TOOLS,
                     timeout=30.0, max_output=10000):
    try:
        from quickjs_rs import Runtime
    except ImportError:
        return TEXT["error"].format(error=TEXT["codemode_missing"])
    from openagentic.cli.tools import TOOLS
    names = set(tool_names if tool_names is not None else [t["function"]["name"] for t in TOOLS])
    names -= {"codemode", "done"}
    outputs = []
    output_size = 0
    calls = 0
    semaphore = asyncio.Semaphore(4)
    mutation_lock = asyncio.Lock()

    def output(value):
        nonlocal output_size
        rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        output_size += len(rendered.encode("utf-8"))
        if output_size > max_output:
            raise ValueError(TEXT["codemode_output"])
        outputs.append(rendered)

    async def call(name, args):
        nonlocal calls
        calls += 1
        if calls > MAX_CALLS:
            raise ValueError(TEXT["codemode_calls"])
        if name not in names:
            raise ValueError(TEXT["unknown_tool"].format(name=name))
        if not isinstance(args, dict):
            raise ValueError(TEXT["tool_arguments"])
        async with semaphore:
            if name in read_only_tools:
                result = await execute(name, args)
            else:
                # Parallel reads; writes and confirmation prompts never overlap.
                async with mutation_lock:
                    result = await execute(name, args)
        if isinstance(result, str) and result.startswith(("[ERROR]", "[REFUSED]")):
            raise ValueError(result)
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
            raise ValueError(TEXT["codemode_output"])
        return result

    try:
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE_BYTES:
            raise ValueError(TEXT["script_limit"])
        with Runtime(memory_limit=64 * 1024 * 1024, stack_limit=512 * 1024) as runtime:
            js_timeout = min(timeout, MAX_JS_SECONDS)
            with runtime.new_context(timeout=js_timeout) as context:
                context.register("__tool", call)
                context.register("text", output)
                context.eval("globalThis.tools = Object.fromEntries(" + json.dumps(sorted(names)) +
                             ".map(name => [name, args => __tool(name, args)])); void 0;")
                async with asyncio.timeout(timeout):
                    result = await context.eval_async("await (async () => {\n" + code + "\n})()", timeout=js_timeout)
                # The engine may let JavaScript absorb a cancelled host promise.
                if asyncio.current_task().cancelling():
                    raise asyncio.CancelledError
                if result is not None:
                    output(result)
        return "\n".join(outputs)
    except Exception as exc:
        return TEXT["error"].format(error=str(exc))
