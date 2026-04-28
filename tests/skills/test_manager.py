"""Test SkillsManager — scanning, querying, seeding, and creation."""

from pathlib import Path

import pytest

from openagentic.skills.manager import (
    Skill,
    SkillError,
    SkillNotFound,
    SkillsManager,
)


class TestSkillsManager:
    @pytest.fixture
    def skill_root(self, tmp_path: Path) -> Path:
        return tmp_path / "skills"

    @pytest.fixture
    def mgr(self, skill_root: Path) -> SkillsManager:
        return SkillsManager(root=skill_root)

    def _write_skill(self, root: Path, slug: str, name: str | None = None,
                     description: str = "test skill", body: str = "# test"):
        d = root / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"""---
name: {name or slug}
description: {description}
---

{body}
""", encoding="utf-8")
        return d / "SKILL.md"

    def test_list_empty(self, mgr: SkillsManager):
        assert mgr.list_skills() == []

    def test_list_one(self, mgr: SkillsManager, skill_root: Path):
        self._write_skill(skill_root, "my-skill", description="test desc")
        skills = mgr.list_skills()
        assert len(skills) == 1
        assert skills[0].slug == "my-skill"
        assert skills[0].description == "test desc"

    def test_list_with_errors(self, mgr: SkillsManager, skill_root: Path):
        self._write_skill(skill_root, "good", description="valid")
        d = skill_root / "bad"
        d.mkdir()
        (d / "SKILL.md").write_text("no frontmatter")
        skills, errors = mgr.list_with_errors()
        assert len(skills) == 1
        assert len(errors) == 1

    def test_get_existing(self, mgr: SkillsManager, skill_root: Path):
        self._write_skill(skill_root, "git-commit", description="commit skill")
        skill = mgr.get("git-commit")
        assert skill.slug == "git-commit"
        assert skill.name == "git-commit"

    def test_get_nonexistent(self, mgr: SkillsManager):
        with pytest.raises(SkillNotFound):
            mgr.get("no-such-skill")

    def test_get_invalid_slug(self, mgr: SkillsManager):
        with pytest.raises(SkillNotFound, match="invalid slug"):
            mgr.get("INVALID slug!")

    def test_get_unreadable(self, mgr: SkillsManager, skill_root: Path):
        d = skill_root / "broken"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("garbage without frontmatter")
        with pytest.raises(SkillNotFound):
            mgr.get("broken")

    def test_create_template(self, mgr: SkillsManager, skill_root: Path):
        path = mgr.create_template("new-skill")
        assert path.exists()
        assert "new-skill" in path.read_text()
        # Verify it's parseable
        skill = mgr.get("new-skill")
        assert skill.slug == "new-skill"

    def test_create_template_already_exists(self, mgr: SkillsManager, skill_root: Path):
        self._write_skill(skill_root, "existing", description="already here")
        with pytest.raises(SkillError, match="already exists"):
            mgr.create_template("existing")

    def test_create_template_invalid_slug(self, mgr: SkillsManager):
        with pytest.raises(SkillError, match="invalid slug"):
            mgr.create_template("Bad Slug!")

    def test_ensure_seeded_creates_marker(self, mgr: SkillsManager):
        """首次播种应创建 .seeded 标记文件。"""
        _ = mgr.ensure_seeded()
        # seeded 可能为空（若 builtin 目录不存在），但 marker 必须存在
        marker = mgr.root / ".seeded"
        assert marker.exists()

    def test_ensure_seeded_is_idempotent(self, mgr: SkillsManager):
        """第二次调用 ensure_seeded 应返回空列表。"""
        mgr.ensure_seeded()
        seeded = mgr.ensure_seeded()
        assert seeded == []

    def test_skill_from_parsed_roundtrip(self, mgr: SkillsManager, skill_root: Path):
        """Skill.from_parsed 应完整保留 ParsedSkill 的所有字段。"""
        path = self._write_skill(skill_root, "roundtrip", description="round trip test",
                                 body="## Steps\n1. do it")
        from openagentic.skills.loader import parse_skill_md
        parsed = parse_skill_md(path)
        skill = Skill.from_parsed(parsed)
        assert skill.slug == parsed.slug
        assert skill.name == parsed.name
        assert skill.description == parsed.description
        assert skill.body == parsed.body
        assert skill.allowed_tools == parsed.allowed_tools
