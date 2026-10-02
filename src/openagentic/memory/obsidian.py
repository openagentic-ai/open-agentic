"""Obsidian-compatible vault access without requiring the desktop application.

Reads Markdown properties and wikilinks as data; never executes note contents.
"""

import re
from pathlib import Path
from urllib.parse import urlencode

import yaml

_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MAX_NOTE_BYTES = 256_000
MAX_NOTES = 2000


class ObsidianVault:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()

    def _path(self, relative: str) -> Path:
        candidate = self.root / relative
        resolved = candidate.resolve()
        if (Path(relative).is_absolute() or ".." in Path(relative).parts
                or not resolved.is_relative_to(self.root)
                or resolved.suffix.lower() != ".md"
                or any(part.startswith(".") for part in Path(relative).parts)):
            raise ValueError("Invalid vault note path")
        return resolved

    def paths(self, folder: str = "") -> list[str]:
        start = (self.root / folder).resolve()
        if not start.is_relative_to(self.root) or not start.exists():
            return []
        paths: list[str] = []
        for path in start.rglob("*.md"):
            relative = path.relative_to(self.root).as_posix()
            try:
                safe = self._path(relative)
                if safe.is_file() and safe.stat().st_size <= MAX_NOTE_BYTES:
                    paths.append(relative)
            except (OSError, ValueError):
                continue
            if len(paths) >= MAX_NOTES:
                break
        return sorted(paths)

    def read(self, relative: str) -> dict:
        path = self._path(relative)
        if path.stat().st_size > MAX_NOTE_BYTES:
            raise ValueError("Vault note is too large")
        text = path.read_text(encoding="utf-8")
        properties: dict = {}
        body = text
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        if match:
            try:
                parsed = yaml.safe_load(match.group(1))
                if isinstance(parsed, dict):
                    properties = parsed
            except yaml.YAMLError:
                pass
            body = text[match.end():].strip()
        title = properties.get("name") or path.stem
        return {
            "path": relative, "name": str(title), "content": body,
            "properties": properties, "links": sorted(set(_LINK.findall(body))),
        }

    def search(self, query: str, top_k: int = 10, folder: str = "") -> list[dict]:
        query = query.strip().lower()
        results = []
        for relative in self.paths(folder):
            try:
                note = self.read(relative)
            except (OSError, ValueError, UnicodeError):
                continue
            searchable = f"{note['content']} {note['properties']}".lower()
            score = searchable.count(query) + note["name"].lower().count(query) * 3
            if query and score == 0:
                continue
            results.append({**note, "content": note["content"][:4000], "score": float(score)})
        return sorted(results, key=lambda note: (-note["score"], note["path"]))[:top_k]

    def backlinks(self, relative: str) -> list[dict]:
        self.read(relative)
        target = relative.removesuffix(".md")
        stem = Path(target).name
        # Unqualified wikilinks are only resolved when the basename is unique.
        unique = sum(Path(path).stem == stem for path in self.paths()) == 1
        results = []
        for path in self.paths():
            try:
                note = self.read(path)
            except (OSError, ValueError, UnicodeError):
                continue
            if any(link.removesuffix(".md") == target or (
                unique and link.removesuffix(".md") == stem
            ) for link in note["links"]):
                results.append({"path": path, "name": note["name"]})
        return results

    def write(self, relative: str, properties: dict, body: str) -> str:
        path = self._path(relative)
        content = "---\n" + yaml.safe_dump(properties, allow_unicode=True, sort_keys=False)
        content += "---\n\n" + body + "\n"
        if len(content.encode("utf-8")) > MAX_NOTE_BYTES:
            raise ValueError("Vault note is too large")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def uri(self, relative: str) -> str:
        # Useful only on a device with this same vault available in Obsidian.
        return "obsidian://open?" + urlencode({"path": str(self._path(relative))})
