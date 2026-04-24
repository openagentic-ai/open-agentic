"""Test file-based MemoryManager (no DB required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openagentic.memory.manager import (
    MemoryEntry,
    MemoryManager,
    estimate_tokens,
    working_memory_compressible,
)


class TestMemoryEntry:
    def test_to_frontmatter_and_back(self):
        entry = MemoryEntry(
            key="test_key", value="test value 中文",
            category="preference", importance=0.8,
        )
        md = entry.to_frontmatter()
        assert "name: test_key" in md
        assert "category: preference" in md
        assert "importance: 0.8" in md
        assert "test value 中文" in md

        parsed = MemoryEntry.from_markdown(md, "test.md")
        assert parsed is not None
        assert parsed.key == "test_key"
        assert parsed.value == "test value 中文"
        assert parsed.category == "preference"
        assert parsed.importance == 0.8


class TestMemoryManager:
    @pytest.fixture
    def mgr(self, tmp_path: Path):
        return MemoryManager(base_dir=tmp_path / ".openagentic" / "memory")

    def test_save_and_search_core(self, mgr: MemoryManager):
        mgr.save_core_memory("lang", "Chinese", "preference", 0.9)
        mgr.save_core_memory("editor", "VS Code", "preference", 0.5)
        mgr.save_core_memory("project", "OpenAgentic", "project_fact", 0.8)

        results = mgr.search_core("Chinese")
        assert len(results) == 1
        assert results[0].key == "lang"

        results = mgr.search_core("editor")
        assert len(results) >= 1

        results = mgr.search_core("", category="project_fact")
        assert len(results) >= 1
        assert results[0].category == "project_fact"

    def test_delete_core(self, mgr: MemoryManager):
        mgr.save_core_memory("tmp", "delete me", "reference")
        assert mgr.delete_core_memory("tmp") is True
        assert mgr.delete_core_memory("nonexistent") is False

    def test_list_core(self, mgr: MemoryManager):
        mgr.save_core_memory("a", "1", "preference", 0.9)
        mgr.save_core_memory("b", "2", "preference", 0.5)
        entries = mgr.list_core()
        assert len(entries) >= 2
        assert entries[0].key == "a"

    def test_save_and_search_episodes(self, mgr: MemoryManager):
        mgr.save_episode("Debug session", "Fixed a null pointer bug", ["debug", "fix"])
        mgr.save_episode("Deploy", "Deployed to production", ["deploy"])

        results = mgr.search_episodes("debug")
        assert len(results) >= 1
        assert "bug" in results[0]["summary"]

        results = mgr.search_episodes("production")
        assert len(results) >= 1

    def test_save_and_search_procedures(self, mgr: MemoryManager):
        mgr.save_procedure(
            "Deploy workflow",
            "Standard deployment steps",
            "deploy, deployment, release, 部署",
            ["Run tests", "Build image", "Push to registry", "Restart service"],
        )

        results = mgr.search_procedures("deploy")
        assert len(results) >= 1

        results = mgr.search_procedures("部署")
        assert len(results) >= 1

    def test_update_index(self, mgr: MemoryManager):
        mgr.save_core_memory("hello", "world", "reference")
        index = mgr._base / "MEMORY.md"
        assert index.exists()
        content = index.read_text()
        assert "hello" in content
        assert "world" in content

    def test_chinese_content(self, mgr: MemoryManager):
        mgr.save_core_memory("用户名", "蔡昊伦", "user_profile", 1.0)
        results = mgr.search_core("蔡昊伦")
        assert len(results) == 1
        assert results[0].value == "蔡昊伦"


class TestTokenEstimation:
    def test_empty(self):
        assert estimate_tokens([]) == 0

    def test_basic(self):
        msgs = [{"role": "user", "content": "你好" * 100}]
        tokens = estimate_tokens(msgs)
        assert tokens > 0
        assert tokens < 200

    def test_compressible(self):
        msgs = [{"role": "user", "content": "x" * 30000}]
        assert working_memory_compressible(msgs, max_tokens=5000)

    def test_not_compressible(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert not working_memory_compressible(msgs, max_tokens=5000)
