"""OpenAgentic File-Based Memory System (Phase 4.5).

Four tiers:
- Working Memory: sliding window + LLM summarization (compression)
- Core Memory: user profile, project facts, preferences, references
- Episodic Memory: cross-session conversation summaries
- Procedural Memory: reusable learned procedures in an Obsidian-compatible vault

Storage: ~/.openagentic/memory/ (file-based, same format as Claude Code MEMORY.md)
Server mode: isolated per-user roots; optional OPENAGENTIC_OBSIDIAN_ROOT for vaults.
"""

from openagentic.memory.manager import MemoryManager

__all__ = ["MemoryManager"]
