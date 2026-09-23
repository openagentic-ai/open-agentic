from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PersonalWorkspace:
    user_id: str
    root: Path

    @classmethod
    def for_user(cls, root: str | Path, user_id: str) -> "PersonalWorkspace":
        safe = "".join(char for char in user_id if char.isalnum() or char in "._-")[:128]
        if not safe:
            raise ValueError("user_id must contain a safe character")
        path = Path(root).expanduser().resolve() / "users" / safe
        path.mkdir(parents=True, exist_ok=True)
        return cls(safe, path)

    def path(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("workspace path escapes user workspace")
        return candidate
