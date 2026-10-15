"""Local append-only conversation trees, independent of model credentials."""

from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import uuid

from openagentic.cli.turn_control import pending_tool_calls

TEXT = json.loads(Path(__file__).with_name("session_messages.json").read_text(encoding="utf-8"))


class SessionStore:
    def __init__(self, root: Path | None = None, cwd: Path | None = None):
        root = root or Path(os.environ.get("OPENAGENTIC_CLI_SESSION_DIR", "~/.openagentic/sessions")).expanduser()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = root / "cli.sqlite3"
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, cwd TEXT NOT NULL, head INTEGER,
                title TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY, session_id TEXT NOT NULL,
                parent INTEGER, kind TEXT NOT NULL, data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS entries_session ON entries(session_id);
        """)
        self.cwd = str((cwd or Path.cwd()).resolve())
        self.id = ""
        self.head: int | None = None
        self._messages: list[dict] = []

    def close(self) -> None:
        self.db.close()

    def create(self) -> str:
        sid = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO sessions(id, cwd) VALUES (?, ?)", (sid, self.cwd))
        self.id, self.head, self._messages = sid, None, []
        return sid

    def list_sessions(self) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM sessions WHERE cwd=? ORDER BY updated DESC, rowid DESC", (self.cwd,),
        )]

    def resume(self, session_id: str | None = None) -> list[dict]:
        candidates = self.list_sessions()
        if session_id:
            candidates = [row for row in candidates if row["id"].startswith(session_id)]
        else:
            candidates = candidates[:1]
        if len(candidates) != 1:
            raise ValueError(TEXT["missing_session"])
        row = candidates[0]
        messages = self._read(row["head"], row["id"])
        self.id, self.head, self._messages = row["id"], row["head"], deepcopy(messages)
        return messages

    def _read(self, node: int | None, sid: str) -> list[dict]:
        entries = []
        while node is not None:
            row = self.db.execute("SELECT * FROM entries WHERE id=? AND session_id=?", (node, sid)).fetchone()
            if row is None:
                raise ValueError(TEXT["missing_node"])
            entries.append(row)
            if row["kind"] == "context":
                break
            node = row["parent"]
        messages = []
        for row in reversed(entries):
            data = json.loads(row["data"])
            if row["kind"] == "context":
                messages = data
            else:
                messages.append(data)
        return messages

    def _check_head(self) -> None:
        row = self.db.execute("SELECT head FROM sessions WHERE id=?", (self.id,)).fetchone()
        if row is None or row["head"] != self.head:
            raise ValueError(TEXT["concurrent_change"])

    def save(self, messages: list[dict]) -> None:
        if messages == self._messages:
            return
        # Lock before checking the head so two CLI processes cannot lose a branch.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._check_head()
            head = self.head
            records: list[tuple[str, dict | list[dict]]]
            if messages[:len(self._messages)] == self._messages:
                records = [("message", m) for m in messages[len(self._messages):]]
            else:
                # Compaction and system-prompt changes are checkpoints, not deletions.
                records = [("context", messages)]
            for kind, data in records:
                cursor = self.db.execute(
                    "INSERT INTO entries(session_id, parent, kind, data) VALUES (?, ?, ?, ?)",
                    (self.id, head, kind, json.dumps(data, ensure_ascii=False)),
                )
                head = cursor.lastrowid
            title = next((str(m.get("content") or "")[:80] for m in messages if m.get("role") == "user"), "")
            self.db.execute(
                "UPDATE sessions SET head=?, title=CASE WHEN title='' THEN ? ELSE title END, updated=CURRENT_TIMESTAMP WHERE id=?",
                (head, title, self.id),
            )
        self.head, self._messages = head, deepcopy(messages)

    def checkout(self, node: int) -> list[dict]:
        messages = self._read(node, self.id)
        if pending_tool_calls(messages):
            raise ValueError(TEXT["pending_tools"])
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._check_head()
            self.db.execute("UPDATE sessions SET head=?, updated=CURRENT_TIMESTAMP WHERE id=?", (node, self.id))
        self.head, self._messages = node, deepcopy(messages)
        return messages

    def fork(self, node: int | None = None) -> list[dict]:
        messages = self._read(self.head if node is None else node, self.id)
        if pending_tool_calls(messages):
            raise ValueError(TEXT["pending_tools"])
        self.create()
        self.save(messages)
        return messages

    def tree(self) -> list[dict]:
        nodes = []
        for row in self.db.execute("SELECT * FROM entries WHERE session_id=? ORDER BY id", (self.id,)):
            data = json.loads(row["data"])
            message = (data[-1] if data else {}) if row["kind"] == "context" else data
            nodes.append({"id": row["id"], "parent": row["parent"],
                          "role": message.get("role", "context"),
                          "preview": str(message.get("content") or "")[:80].replace("\n", " "),
                          "active": row["id"] == self.head})
        return nodes
