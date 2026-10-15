"""LF-delimited JSON subprocess protocol for the Python AgentSession SDK."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any

from openagentic.runtime.agent import AgentSession
from openagentic.runtime.extensions import Extensions, TEXT

MAX_FRAME = 8 * 1024 * 1024


async def serve(session: AgentSession, incoming: asyncio.Queue, write):
    tasks: dict = {}
    async def run_prompt(rid, text):
        try:
            result = await session.prompt(text)
            write({"id": rid, "result": result})
        except asyncio.CancelledError:
            write({"id": rid, "error": {"code": "cancelled", "message": TEXT["run_cancelled"]}})
        except Exception as exc:
            write({"id": rid, "error": {"code": "run_failed", "message": str(exc)}})
        finally:
            tasks.pop(rid, None)

    try:
        await session.start()
        while True:
            line = await incoming.get()
            if line is None:
                break
            rid = None
            result: Any
            try:
                if len(line) > MAX_FRAME:
                    raise ValueError(TEXT["frame_limit"])
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError(TEXT["request_type"])
                rid = request.get("id")
                if not isinstance(rid, (str, int, type(None))):
                    raise ValueError(TEXT["id_type"])
                method, params = request["method"], request.get("params", {})
                if not isinstance(params, dict):
                    raise ValueError(TEXT["params_type"])
                if method == "prompt":
                    if tasks or session.busy:
                        raise RuntimeError(TEXT["busy"])
                    text = params["text"]
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError(TEXT["prompt_type"])
                    tasks[rid] = asyncio.create_task(run_prompt(rid, text))
                    # Establish the run before consuming an already-buffered cancel.
                    await asyncio.sleep(0)
                    continue
                elif method in {"steer", "follow_up"}:
                    text = params["text"]
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError(TEXT["message_type"])
                    getattr(session, method)(text)
                    result = True
                elif method == "cancel":
                    session.cancel()
                    result = True
                elif method == "state":
                    result = {"session_id": session.id, "busy": session.busy, "messages": session.messages}
                elif method == "tree":
                    result = session.tree()
                elif method == "checkout":
                    result = session.checkout(int(params["node"]))
                elif method == "command":
                    result = await session.command(params["name"], params.get("args", ""))
                elif method == "close":
                    await session.close()
                    write({"id": rid, "result": True})
                    break
                else:
                    raise ValueError(TEXT["rpc_method"].format(method=method))
                write({"id": rid, "result": result})
            except Exception as exc:
                write({"id": rid, "error": {"code": "invalid_request", "message": str(exc)}})
    finally:
        await session.close()
        if tasks:
            await asyncio.gather(*list(tasks.values()), return_exceptions=True)


async def stdio_main(*, model, api_base=None, api_key=None, extension_paths=(),
                     session_dir=None, resume=None, codemode=False, system_prompt=None, provider="auto"):
    # Reserve stdout for JSON even when providers/extensions print directly.
    wire = sys.stdout
    sys.stdout = sys.stderr
    def write(value):
        wire.write(json.dumps(value, ensure_ascii=False) + "\n")
        wire.flush()
    session = None
    try:
        extensions = Extensions()
        extensions.load(extension_paths)
        if model.partition("/")[0] not in extensions.providers:
            from openagentic.cli.providers import find_profile, resolve_provider
            profile = find_profile(resolve_provider(provider, model))
            if profile:
                api_base = api_base or profile["api_base"]
                api_key = api_key or profile["api_key"]
        session = AgentSession(model=model, api_base=api_base, api_key=api_key,
            extensions=extensions, session_dir=session_dir, resume=resume,
            codemode=codemode, system_prompt=system_prompt,
            on_event=lambda event: write({"event": event}))
        loop = asyncio.get_running_loop()
        incoming = asyncio.Queue()
        stdin_fd = sys.stdin.fileno()
        def read():
            # Raw reads avoid holding BufferedReader's lock during interpreter shutdown.
            pending = b""
            oversized = False
            def enqueue(line):
                if not loop.is_closed():
                    loop.call_soon_threadsafe(incoming.put_nowait, line)
            try:
                while chunk := os.read(stdin_fd, 65536):
                    pending += chunk
                    while b"\n" in pending:
                        line, pending = pending.split(b"\n", 1)
                        enqueue(b"x" * (MAX_FRAME + 1) if oversized else line)
                        oversized = False
                    if len(pending) > MAX_FRAME:
                        pending = b""
                        oversized = True
                if pending or oversized:
                    enqueue(b"x" * (MAX_FRAME + 1) if oversized else pending)
            except (OSError, RuntimeError):
                pass  # EOF or the event loop has already closed.
            finally:
                if not loop.is_closed():
                    try:
                        enqueue(None)
                    except RuntimeError:
                        pass
        threading.Thread(target=read, daemon=True).start()
        await serve(session, incoming, write)
    finally:
        if session:
            await session.close()
        sys.stdout = wire


def main():
    parser = argparse.ArgumentParser(description="OpenAgentic JSONL RPC")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-base")
    parser.add_argument("--extension", action="append", default=[])
    parser.add_argument("--session-dir", type=Path)
    parser.add_argument("--resume")
    parser.add_argument("--codemode", action="store_true")
    args = parser.parse_args()
    asyncio.run(stdio_main(model=args.model, api_base=args.api_base,
        extension_paths=args.extension, session_dir=args.session_dir,
        resume=args.resume, codemode=args.codemode))


if __name__ == "__main__":
    main()
