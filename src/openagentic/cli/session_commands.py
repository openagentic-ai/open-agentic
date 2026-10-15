"""Small session commands shared by the interactive shell."""

from rich.console import Console

from openagentic.cli._patchable_stdout import _patchable_stdout
from openagentic.cli.sessions import SessionStore, TEXT
from openagentic.cli.turn_control import finish_interrupted_tools

_console = Console(file=_patchable_stdout)
COMMANDS = ["/sessions", "/resume", "/new", "/session", "/tree", "/fork"]


def handle_session_command(text: str, store: SessionStore, messages: list[dict], rebuild) -> bool:
    command, _, arg = text.partition(" ")
    if command not in COMMANDS:
        return False
    arg = arg.strip()
    try:
        if command == "/sessions" or (command == "/resume" and not arg):
            rows = store.list_sessions()
            if not rows:
                _console.print(TEXT["empty"], markup=False)
            for row in rows:
                _console.print(TEXT["session_row"].format(**row), markup=False)
        elif command == "/session":
            _console.print(TEXT["saved"].format(id=store.id), markup=False)
        elif command == "/tree" and not arg:
            for row in store.tree():
                _console.print(TEXT["node_row"].format(marker="*" if row["active"] else " ", **row), markup=False)
        elif command == "/tree":
            messages[:] = store.checkout(int(arg))
            rebuild()
            _console.print(TEXT["branched"].format(node=arg), markup=False)
        elif command == "/resume":
            messages[:] = store.resume(arg)
            finish_interrupted_tools(messages, TEXT["interrupted"])
            rebuild()
            _console.print(TEXT["restored"].format(id=store.id, count=len(messages)), markup=False)
        elif command == "/fork":
            messages[:] = store.fork(int(arg) if arg else None)
            rebuild()
            _console.print(TEXT["new"].format(id=store.id), markup=False)
        else:
            store.create()
            messages[:] = [{"role": "system", "content": ""}]
            rebuild()
            _console.print(TEXT["new"].format(id=store.id), markup=False)
    except (ValueError, OSError) as exc:
        _console.print(TEXT["failed"].format(error=exc), markup=False)
    return True
