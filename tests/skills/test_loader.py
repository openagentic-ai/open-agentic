"""Test Skills loader — SKILL.md frontmatter parsing and discovery."""

from pathlib import Path

import pytest

from openagentic.skills.loader import (
    ParsedSkill,
    SkillParseError,
    is_valid_slug,
    parse_skill_md,
    discover_skills,
)


VALID_SKILL_MD = """---
name: git-commit
description: Generate conventional commit messages
allowed-tools: ["run_command"]
---

# git-commit

## When to use
- When the user asks to commit
"""

NO_FRONTMATTER = """# git-commit

This skill has no frontmatter.
"""

MISSING_NAME = """---
description: missing name field
---

# test
"""

MISSING_DESC = """---
name: test-skill
---

# test
"""

INVALID_YAML = """---
name: [unclosed
---

# test
"""

NOT_A_MAPPING = """---
- list
- not
- mapping
---

# test
"""

MISMATCHED_NAME = """---
name: wrong-name
description: some desc
---

# test
"""


class TestIsValidSlug:
    def test_valid_slugs(self):
        assert is_valid_slug("git-commit")
        assert is_valid_slug("code-review")
        assert is_valid_slug("debug-trace")
        assert is_valid_slug("a")

    def test_invalid_slugs(self):
        assert not is_valid_slug("")
        assert not is_valid_slug("Git-Commit")
        assert not is_valid_slug("git_commit")
        assert not is_valid_slug("git commit")
        assert not is_valid_slug("123-start")
        assert not is_valid_slug("-start")


class TestParseSkillMd:
    def test_parse_valid(self, tmp_path: Path):
        slug_dir = tmp_path / "git-commit"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(VALID_SKILL_MD)

        parsed = parse_skill_md(skill_md)
        assert parsed.slug == "git-commit"
        assert parsed.name == "git-commit"
        assert "conventional commit" in parsed.description
        assert parsed.allowed_tools == ["run_command"]
        assert "git-commit" in parsed.body

    def test_parse_missing_file(self, tmp_path: Path):
        fake = tmp_path / "nonexistent" / "SKILL.md"
        with pytest.raises(FileNotFoundError):
            parse_skill_md(fake)

    def test_parse_no_frontmatter(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(NO_FRONTMATTER)

        with pytest.raises(SkillParseError, match="frontmatter"):
            parse_skill_md(skill_md)

    def test_parse_missing_name(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(MISSING_NAME)

        with pytest.raises(SkillParseError, match="name"):
            parse_skill_md(skill_md)

    def test_parse_missing_description(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(MISSING_DESC)

        with pytest.raises(SkillParseError, match="description"):
            parse_skill_md(skill_md)

    def test_parse_invalid_yaml(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(INVALID_YAML)

        with pytest.raises(SkillParseError, match="YAML"):
            parse_skill_md(skill_md)

    def test_parse_not_mapping(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(NOT_A_MAPPING)

        with pytest.raises(SkillParseError, match="mapping"):
            parse_skill_md(skill_md)

    def test_parse_name_mismatch(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(MISMATCHED_NAME)

        with pytest.raises(SkillParseError, match="directory"):
            parse_skill_md(skill_md)

    def test_parse_invalid_slug(self, tmp_path: Path):
        slug_dir = tmp_path / "Invalid_Slug"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        # Fix the name to match the invalid slug
        skill_md.write_text("""---
name: Invalid_Slug
description: test
---

# test
""")
        with pytest.raises(SkillParseError, match="slug"):
            parse_skill_md(skill_md)

    def test_allowed_tools_none_if_missing(self, tmp_path: Path):
        slug_dir = tmp_path / "no-tools"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text("""---
name: no-tools
description: skill without tool restrictions
---

# no-tools
""")
        parsed = parse_skill_md(skill_md)
        assert parsed.allowed_tools is None

    def test_allowed_tools_must_be_strings(self, tmp_path: Path):
        slug_dir = tmp_path / "bad-tools"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text("""---
name: bad-tools
description: test
allowed-tools: [1, 2, 3]
---

# test
""")
        with pytest.raises(SkillParseError, match="list of strings"):
            parse_skill_md(skill_md)

    def test_metadata_one_line(self, tmp_path: Path):
        slug_dir = tmp_path / "test-skill"
        slug_dir.mkdir()
        skill_md = slug_dir / "SKILL.md"
        skill_md.write_text(VALID_SKILL_MD)
        # Note: this file uses slug "git-commit" but placed in "test-skill" dir,
        # causing name mismatch. Let's write a valid one.
        valid = """---
name: test-skill
description: Test skill for metadata
---

# test
"""
        skill_md.write_text(valid)
        parsed = parse_skill_md(skill_md)
        line = parsed.metadata_one_line
        assert "test-skill" in line
        assert "Test skill for metadata" in line


class TestDiscoverSkills:
    def test_empty_dir(self, tmp_path: Path):
        skills, errors = discover_skills(tmp_path)
        assert skills == []
        assert errors == []

    def test_non_existent_dir(self, tmp_path: Path):
        skills, errors = discover_skills(tmp_path / "nope")
        assert skills == []
        assert errors == []

    def test_single_valid_skill(self, tmp_path: Path):
        slug_dir = tmp_path / "my-skill"
        slug_dir.mkdir()
        (slug_dir / "SKILL.md").write_text("""---
name: my-skill
description: my description
---

# my skill body
""")
        skills, errors = discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].slug == "my-skill"
        assert errors == []

    def test_mixed_valid_and_invalid(self, tmp_path: Path):
        # Valid skill
        d1 = tmp_path / "good-skill"
        d1.mkdir()
        (d1 / "SKILL.md").write_text("""---
name: good-skill
description: valid
---

# good
""")
        # Invalid skill (no frontmatter)
        d2 = tmp_path / "bad-skill"
        d2.mkdir()
        (d2 / "SKILL.md").write_text("# no frontmatter")

        skills, errors = discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].slug == "good-skill"
        assert len(errors) == 1

    def test_skips_dirs_without_skill_md(self, tmp_path: Path):
        d = tmp_path / "not-a-skill"
        d.mkdir()
        # no SKILL.md inside
        skills, errors = discover_skills(tmp_path)
        assert skills == []

    def test_skills_sorted_by_slug(self, tmp_path: Path):
        for slug in ["c-skill", "a-skill", "b-skill"]:
            d = tmp_path / slug
            d.mkdir()
            (d / "SKILL.md").write_text(f"""---
name: {slug}
description: test
---

# {slug}
""")
        skills, _ = discover_skills(tmp_path)
        slugs = [s.slug for s in skills]
        assert slugs == ["a-skill", "b-skill", "c-skill"]
