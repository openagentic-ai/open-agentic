"""Smoke tests for Phase 5.5 P1 features: /diff, /review, builtin SKILLs."""

from pathlib import Path

import pytest

from openagentic.skills.manager import SkillsManager, _BUILTIN_DIR
from openagentic.skills.loader import discover_skills


# ---------------------------------------------------------------------------
# /diff & /review handlers
# ---------------------------------------------------------------------------


class TestDiffHandler:
    def test_imports(self):
        from openagentic.cli.slash_commands import _handle_diff, _handle_review
        assert callable(_handle_diff)
        assert callable(_handle_review)

    def test_diff_registered_in_slash_commands(self):
        from openagentic.cli.slash_commands import SLASH_COMMANDS
        assert "/diff" in SLASH_COMMANDS
        assert "/review" in SLASH_COMMANDS

    def test_diff_no_args_does_not_crash(self, capsys, monkeypatch, tmp_path):
        """/diff in a non-git dir should handle gracefully."""
        from openagentic.cli.slash_commands import _handle_diff

        # Simulate git not found / no repo
        monkeypatch.chdir(tmp_path)
        _handle_diff("")
        capsys.readouterr()  # flush output
        # Should not raise; may show error or "no changes"
        assert True  # 不崩溃即通过

    def test_review_queue_injection(self):
        """_handle_review should inject a message into the queue."""
        import asyncio
        from unittest import mock
        from openagentic.cli.slash_commands import _handle_review

        async def _run():
            q = asyncio.Queue()
            # Mock subprocess to return empty diff (no changes)
            with mock.patch("subprocess.run") as m_run:
                m_run.return_value = mock.MagicMock(
                    returncode=0, stdout="", stderr=""
                )
                await _handle_review("", q)
            # Queue should be empty (no diff = no injection)
            assert q.empty()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Builtin SKILLs — all 6 present and valid
# ---------------------------------------------------------------------------


class TestBuiltinSkills:
    BUILTIN_SLUGS = [
        "git-commit", "code-review", "debug-trace",
        "security-review", "simplify", "batch",
    ]

    def test_all_6_builtins_exist(self):
        parsed, errors = discover_skills(_BUILTIN_DIR)
        slugs = {p.slug for p in parsed}
        assert not errors, f"Parse errors: {errors}"
        for slug in self.BUILTIN_SLUGS:
            assert slug in slugs, f"Missing builtin: {slug}"

    def test_each_builtin_has_valid_frontmatter(self):
        parsed, errors = discover_skills(_BUILTIN_DIR)
        assert not errors, f"Parse errors: {errors}"
        for p in parsed:
            assert p.name == p.slug, f"{p.slug}: name mismatch"
            assert len(p.description) > 10, f"{p.slug}: description too short"
            assert len(p.body) > 100, f"{p.slug}: body too short"

    def test_incremental_seeding(self, tmp_path: Path):
        """New builtins should be seeded even if .seeded already exists."""
        mgr = SkillsManager(root=tmp_path)
        # Simulate old-style .seeded with only 3 slugs
        (tmp_path / ".seeded").write_text(
            "git-commit\ncode-review\ndebug-trace\n", encoding="utf-8"
        )
        new_slugs = mgr.ensure_seeded()
        # The 3 new builtins should be seeded
        assert "security-review" in new_slugs
        assert "simplify" in new_slugs
        assert "batch" in new_slugs

    def test_seeded_file_format(self, tmp_path: Path):
        """After seeding, .seeded should list all 6 slugs."""
        mgr = SkillsManager(root=tmp_path)
        mgr.ensure_seeded()
        content = (tmp_path / ".seeded").read_text(encoding="utf-8")
        for slug in self.BUILTIN_SLUGS:
            assert slug in content


# ---------------------------------------------------------------------------
# Feishu card utils
# ---------------------------------------------------------------------------


class TestFeishuCardUtils:
    @pytest.mark.skip(reason="markdown table 渲染已改为飞书 bitable 工具，不再走卡片 markdown parser")
    def test_markdown_no_table(self):
        from extensions.channels.feishu_card_utils import (
            markdown_to_card_elements, has_table,
        )
        assert not has_table("hello world")
        els = markdown_to_card_elements("hello world")
        assert len(els) == 1
        assert els[0]["tag"] == "div"

    @pytest.mark.skip(reason="markdown table 渲染已改为飞书 bitable 工具，不再走卡片 markdown parser")
    def test_markdown_with_table(self):
        from extensions.channels.feishu_card_utils import (
            markdown_to_card_elements, has_table,
        )
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        assert has_table(md)
        els = markdown_to_card_elements(md)
        assert any(e["tag"] == "column_set" for e in els)

    def test_build_card_functions(self):
        from extensions.channels.feishu_card_utils import (
            build_thinking_card, build_answer_card,
        )
        card = build_thinking_card()
        assert card["header"]["title"]["content"] == "OpenAgentic"
        assert card["config"]["update_multi"] is True

        card = build_answer_card("Hello **world**")
        assert any(e["tag"] == "hr" for e in card["elements"])
        assert any(e["tag"] == "note" for e in card["elements"])
