"""File-based Memory Manager for the CLI.

Organizes memory files at ~/.openagentic/memory/ with the same
frontmatter+markdown format as Claude Code's memory system.

Directory layout:
    ~/.openagentic/memory/
        MEMORY.md           # index file
        core/
            user_profile/    # one .md per memory entry
            project_fact/
            preference/
            reference/
        episodes/            # one .md per episode
        procedures/          # one .md per procedure
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Known categories for core memory (mirrors Claude Code's types)
CORE_CATEGORIES = ["user_profile", "project_fact", "preference", "reference"]

# Frontmatter pattern: ---\nkey: value\n...\n---
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _default_memory_dir() -> Path:
    """Resolve the memory root directory."""
    return Path.home() / ".openagentic" / "memory"


@dataclass
class MemoryEntry:
    """A single memory record in file-based storage."""
    key: str
    value: str
    category: str = "reference"
    importance: float = 0.5
    created: str = ""
    updated: str = ""
    file_path: str = ""

    def to_frontmatter(self) -> str:
        now = datetime.now(timezone.utc).isoformat()
        return (
            "---\n"
            f"name: {self.key}\n"
            f"description: {self.value[:80].replace(chr(10), ' ')}\n"
            f"type: core\n"
            f"category: {self.category}\n"
            f"importance: {self.importance}\n"
            f"created: {self.created or now}\n"
            f"updated: {now}\n"
            "---\n\n"
            f"{self.value}\n"
        )

    @classmethod
    def from_markdown(cls, content: str, file_path: str = "") -> MemoryEntry | None:
        m = _FM_RE.match(content)
        if not m:
            return None
        fm_text = m.group(1)
        body = content[m.end():].strip()
        fm: dict[str, str] = {}
        for line in fm_text.split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
        return cls(
            key=fm.get("name", Path(file_path).stem),
            value=body,
            category=fm.get("category", "reference"),
            importance=float(fm.get("importance", 0.5)),
            created=fm.get("created", ""),
            updated=fm.get("updated", ""),
            file_path=file_path,
        )


class MemoryManager:
    """CRUD + search for file-based memory.

    Usage (CLI path, no FastAPI deps)::

        mgr = MemoryManager()
        await mgr.save_core_memory("preferred_lang", "Chinese", "preference")
        results = await mgr.search_core("语言")
        await mgr.save_episode("对话摘要...", tags=["debug"])
        episodes = await mgr.search_episodes("bug 修复")
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or _default_memory_dir()

    # ------------------------------------------------------------------
    # Core Memory
    # ------------------------------------------------------------------

    def _core_dir(self, category: str) -> Path:
        return self._base / "core" / category

    def save_core_memory(
        self,
        key: str,
        value: str,
        category: str = "reference",
        importance: float = 0.5,
    ) -> str:
        """Save a core memory entry. Returns the file path."""
        if category not in CORE_CATEGORIES:
            category = "reference"
        d = self._core_dir(category)
        d.mkdir(parents=True, exist_ok=True)

        # Sanitize key to a safe filename
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)[:64]
        file_path = d / f"{safe_name}.md"

        # Check if updating existing entry
        old_created = ""
        if file_path.exists():
            old = MemoryEntry.from_markdown(file_path.read_text(encoding="utf-8"), str(file_path))
            if old:
                old_created = old.created

        entry = MemoryEntry(
            key=key, value=value, category=category,
            importance=importance, created=old_created,
            file_path=str(file_path),
        )
        file_path.write_text(entry.to_frontmatter(), encoding="utf-8")
        self._update_index()
        return str(file_path)

    def delete_core_memory(self, key: str) -> bool:
        """Delete a core memory entry by key. Returns True if found."""
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)[:64]
        found = False
        for cat in CORE_CATEGORIES:
            fp = self._core_dir(cat) / f"{safe_name}.md"
            if fp.exists():
                fp.unlink()
                found = True
        if found:
            self._update_index()
        return found

    def search_core(
        self, query: str, category: str | None = None, top_k: int = 10,
    ) -> list[MemoryEntry]:
        """Simple text search over core memory entries."""
        results: list[tuple[MemoryEntry, int]] = []
        cats = [category] if category else CORE_CATEGORIES
        query_lower = query.lower()

        for cat in cats:
            d = self._core_dir(cat)
            if not d.exists():
                continue
            for fp in sorted(d.glob("*.md")):
                content = fp.read_text(encoding="utf-8")
                entry = MemoryEntry.from_markdown(content, str(fp))
                if entry is None:
                    continue
                # Score by keyword match count
                score = (content.lower().count(query_lower)
                         + entry.key.lower().count(query_lower) * 2)
                if score > 0:
                    results.append((entry, score))
        results.sort(key=lambda x: (-x[1], x[0].importance))
        return [e for e, _ in results[:top_k]]

    def list_core(self, category: str | None = None, limit: int = 20) -> list[MemoryEntry]:
        """List core memory entries, sorted by importance desc."""
        entries: list[MemoryEntry] = []
        cats = [category] if category else CORE_CATEGORIES
        for cat in cats:
            d = self._core_dir(cat)
            if not d.exists():
                continue
            for fp in sorted(d.glob("*.md")):
                entry = MemoryEntry.from_markdown(fp.read_text(encoding="utf-8"), str(fp))
                if entry:
                    entries.append(entry)
        entries.sort(key=lambda e: (-e.importance, e.updated))
        return entries[:limit]

    # ------------------------------------------------------------------
    # Episodic Memory
    # ------------------------------------------------------------------

    def _episodes_dir(self) -> Path:
        return self._base / "episodes"

    def save_episode(
        self, title: str, summary: str, tags: list[str] | None = None,
    ) -> str:
        """Save an episode (conversation/task summary)."""
        d = self._episodes_dir()
        d.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", title)[:48]
        uid = uuid.uuid4().hex[:8]
        fp = d / f"{date_str}-{slug}-{uid}.md"

        tag_text = ", ".join(tags) if tags else ""
        content = (
            "---\n"
            f"name: {title}\n"
            f"description: {summary[:120].replace(chr(10), ' ')}\n"
            f"type: episode\n"
            f"tags: [{tag_text}]\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            "---\n\n"
            f"# {title}\n\n"
            f"{summary}\n"
        )
        fp.write_text(content, encoding="utf-8")
        self._update_index()
        return str(fp)

    def search_episodes(
        self, query: str, top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Keyword search over episodes, ranked by recency + match count."""
        d = self._episodes_dir()
        if not d.exists():
            return []
        results: list[tuple[dict, int]] = []
        query_lower = query.lower()
        for fp in sorted(d.glob("*.md"), reverse=True):  # newest first
            content = fp.read_text(encoding="utf-8")
            score = content.lower().count(query_lower)
            if score > 0:
                m = _FM_RE.match(content)
                body = content[m.end():].strip() if m else content
                results.append(({
                    "title": fp.stem,
                    "summary": body[:500],
                    "file": str(fp),
                }, score))
        results.sort(key=lambda x: -x[1])
        return [r for r, _ in results[:top_k]]

    # ------------------------------------------------------------------
    # Procedural Memory
    # ------------------------------------------------------------------

    def _procedures_dir(self) -> Path:
        return self._base / "procedures"

    def save_procedure(
        self, name: str, description: str,
        trigger_pattern: str, steps: list[str],
    ) -> str:
        """Save a reusable procedure."""
        d = self._procedures_dir()
        d.mkdir(parents=True, exist_ok=True)

        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)[:64]
        fp = d / f"{safe_name}.md"

        steps_text = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
        content = (
            "---\n"
            f"name: {name}\n"
            f"description: {description[:120]}\n"
            f"type: procedure\n"
            f"trigger_pattern: {trigger_pattern[:200]}\n"
            f"success_count: 0\n"
            f"failure_count: 0\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            "---\n\n"
            f"# {name}\n\n"
            f"{description}\n\n"
            f"## Trigger\n{trigger_pattern}\n\n"
            f"## Steps\n{steps_text}\n"
        )
        fp.write_text(content, encoding="utf-8")
        self._update_index()
        return str(fp)

    def search_procedures(
        self, query: str, top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Keyword search over procedures."""
        d = self._procedures_dir()
        if not d.exists():
            return []
        results: list[tuple[dict, int]] = []
        query_lower = query.lower()
        for fp in sorted(d.glob("*.md")):
            content = fp.read_text(encoding="utf-8")
            score = (content.lower().count(query_lower)
                     + fp.stem.lower().count(query_lower) * 3)
            if score > 0:
                m = _FM_RE.match(content)
                body = content[m.end():].strip() if m else content
                results.append(({
                    "name": fp.stem,
                    "content": body[:500],
                    "file": str(fp),
                }, score))
        results.sort(key=lambda x: -x[1])
        return [r for r, _ in results[:top_k]]

    # ------------------------------------------------------------------
    # Index maintenance
    # ------------------------------------------------------------------

    def _update_index(self) -> None:
        """Rebuild MEMORY.md index (mirrors Claude Code format)."""
        lines = ["# OpenAgentic Memory Index\n"]
        lines.append(f"> Auto-generated at {datetime.now(timezone.utc).isoformat()}\n")

        # Core memory entries
        core = self._sync_list_core()
        if core:
            lines.append("## Core Memory")
            for entry in core:
                cat_label = entry.category.replace("_", " ").title()
                lines.append(
                    f"- [{entry.key}](core/{entry.category}/{Path(entry.file_path).name})"
                    f" — {entry.value[:100].replace(chr(10), ' ')}"
                    f" `[{cat_label}]`"
                )
            lines.append("")

        # Episodes
        ep_dir = self._episodes_dir()
        if ep_dir.exists():
            eps = sorted(ep_dir.glob("*.md"), reverse=True)[:20]
            if eps:
                lines.append("## Episodes")
                for ep in eps:
                    content = ep.read_text(encoding="utf-8")
                    entry = MemoryEntry.from_markdown(content, str(ep))
                    title = entry.key if entry else ep.stem
                    lines.append(f"- [{title}](episodes/{ep.name})")
                lines.append("")

        # Procedures
        proc_dir = self._procedures_dir()
        if proc_dir.exists():
            procs = sorted(proc_dir.glob("*.md"))
            if procs:
                lines.append("## Procedures")
                for p in procs:
                    content = p.read_text(encoding="utf-8")
                    entry = MemoryEntry.from_markdown(content, str(p))
                    name = entry.key if entry else p.stem
                    lines.append(f"- [{name}](procedures/{p.name})")
                lines.append("")

        index = self._base / "MEMORY.md"
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _sync_list_core(self) -> list[MemoryEntry]:
        """List all core entries for index generation (synchronous)."""
        entries: list[MemoryEntry] = []
        for cat in CORE_CATEGORIES:
            d = self._core_dir(cat)
            if not d.exists():
                continue
            for fp in sorted(d.glob("*.md")):
                entry = MemoryEntry.from_markdown(fp.read_text(encoding="utf-8"), str(fp))
                if entry:
                    entries.append(entry)
        entries.sort(key=lambda e: (-e.importance, e.updated))
        return entries


# ------------------------------------------------------------------
# Working Memory (token budget + compression)
# ------------------------------------------------------------------

def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimation: chars / 4 (conservative for CJK)."""
    total = 0
    for msg in messages:
        content = msg.get("content", "") or ""
        total += max(1, len(content) // 3)  # /3 for CJK-heavy text
        for tc in msg.get("tool_calls", []) or []:
            total += 100
    return total


def working_memory_compressible(
    messages: list[dict],
    max_tokens: int = 6000,
) -> bool:
    """Check if working memory needs compression."""
    return estimate_tokens(messages) > max_tokens


async def compress_working_memory(
    messages: list[dict],
    keep_recent: int = 8,
    model: str = "",
    api_base: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Compress old messages into a summary, keep recent ones.

    Uses LiteLLM to generate a cumulative summary of messages beyond
    the keep_recent window. The system prompt (index 0) is preserved.
    Returns a new messages list.
    """
    if len(messages) <= keep_recent + 4:
        return messages  # not enough to compress

    # Messages to compress: everything between system (idx 0) and recent window
    old = messages[1:-keep_recent]
    recent = messages[-keep_recent:]

    # Build summarization prompt
    conversation_text = ""
    for m in old:
        role = m.get("role", "?")
        content = m.get("content", "") or ""
        if role == "tool":
            content = content[:300]  # truncate long tool results
        conversation_text += f"[{role}]: {content}\n"

    # Check for existing summary in old messages
    existing_summary = ""
    for m in old:
        if m.get("role") == "system" and "[Conversation Summary]" in (m.get("content") or ""):
            existing_summary = m.get("content", "")
            break

    summary_prefix = (
        "Previous summary:\n" + existing_summary + "\n\n"
    ) if existing_summary else ""

    summarize_prompt = (
        f"{summary_prefix}"
        "Summarize the conversation above in 3-6 bullet points covering:\n"
        "- Key user goals and requests\n"
        "- Important decisions or outcomes\n"
        "- Any facts about the user or project worth remembering\n"
        "- Errors encountered and how they were resolved\n\n"
        "Return ONLY the bullet points, in Chinese if the conversation was in Chinese.\n"
        "对话记录:\n"
        f"{conversation_text[-6000:]}\n"
    )

    try:
        from openagentic.cli.llm import litellm_chat
        resp = await litellm_chat(
            [{"role": "user", "content": summarize_prompt}],
            model=model or "deepseek/deepseek-v4-flash",
            api_base=api_base,
            api_key=api_key,
        )
        summary = resp.get("message", {}).get("content", "") or ""
    except Exception:
        # If summarization fails, just truncate
        summary = "[Summarization failed — conversation truncated]"

    # Rebuild messages: system + summary + recent
    compressed = [messages[0]]  # keep system prompt
    compressed.append({
        "role": "system",
        "content": f"[Conversation Summary]\n{summary}",
    })
    compressed.extend(recent)
    return compressed
