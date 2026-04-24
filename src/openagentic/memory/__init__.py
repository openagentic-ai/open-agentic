"""OpenAgentic File-Based Memory System (Phase 4.5).

Four tiers:
- Working Memory: sliding window + LLM summarization (compression)
- Core Memory: user profile, project facts, preferences, references
- Episodic Memory: cross-session conversation summaries
- Procedural Memory: reusable learned procedures

Storage: ~/.openagentic/memory/ (file-based, same format as Claude Code MEMORY.md)
Future: PostgreSQL + pgvector for server mode (see README Phase 4.5 roadmap).
"""

from openagentic.memory.manager import MemoryManager

__all__ = ["MemoryManager"]
