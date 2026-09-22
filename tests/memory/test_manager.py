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
        mgr.save_core_memory("用户名", "张三", "user_profile", 1.0)
        results = mgr.search_core("张三")
        assert len(results) == 1
        assert results[0].value == "张三"


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


class TestRetrievalScores:
    """检索分数契约。

    三个检索函数原先都算了 score 再丢弃（只用于内部排序）。
    「上下文够不够」的判定需要这个信号，所以要把它们暴露出来——
    且不能让现有调用方（按 key 取值的那些）受影响。
    """

    @pytest.fixture
    def mgr(self, tmp_path: Path):
        return MemoryManager(base_dir=tmp_path / ".openagentic" / "memory")

    def test_search_core_exposes_score(self, mgr: MemoryManager):
        mgr.save_core_memory("lang", "Chinese", "preference", 0.9)
        res = mgr.search_core("Chinese")
        assert res, "应该搜到"
        assert hasattr(res[0], "score"), "core 检索要暴露 score"
        assert res[0].score > 0

    def test_search_episodes_exposes_score(self, mgr: MemoryManager):
        mgr.save_episode("部署经验", "用 systemd 管服务", ["deploy"])
        res = mgr.search_episodes("systemd")
        assert res
        assert "score" in res[0]
        assert res[0]["score"] > 0

    def test_search_procedures_exposes_score(self, mgr: MemoryManager):
        mgr.save_procedure("回滚流程", "如何回滚", "服务挂了", ["stop", "start"])
        res = mgr.search_procedures("回滚")
        assert res
        assert "score" in res[0]
        assert res[0]["score"] > 0

    def test_existing_key_access_still_works(self, mgr: MemoryManager):
        """加 score 不能影响按 key 取值的现有调用方。

        注意既有行为：episode 的 `title` 是**文件名 stem**（日期 slug），
        非 ASCII 名字会被 slug 成 `____`，真实标题在 summary 正文里。
        本用例只锁「键还在、能被取值」，不锁 slug 细节。
        """
        mgr.save_episode("部署经验", "内容A", [])
        ep = mgr.search_episodes("内容A")[0]
        assert set(ep) >= {"title", "summary", "file"}
        assert "内容A" in ep["summary"]

        mgr.save_procedure("回滚流程", "描述B", "触发B", ["步骤1"])
        proc = mgr.search_procedures("描述B")[0]
        assert set(proc) >= {"name", "content", "file"}
        assert "描述B" in proc["content"]

    def test_score_ordering_preserved(self, mgr: MemoryManager):
        """分数暴露后排序语义不变：命中多的仍在前。"""
        mgr.save_episode("弱命中", "关键词只出现一次", [])
        mgr.save_episode("强命中", "关键词 关键词 关键词 关键词", [])
        res = mgr.search_episodes("关键词")
        assert len(res) == 2
        assert res[0]["score"] >= res[1]["score"]
