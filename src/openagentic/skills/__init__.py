"""模块说明（中文）：`src/openagentic/skills/__init__.py`。

Skills 系统：基于文件的领域 SOP（Claude Code 风格）。

形态：每个 skill 是 ~/.openagentic/skills/<slug>/SKILL.md，frontmatter 含
name/description/allowed-tools，正文是给模型读的"操作手册"。
启动时扫描 metadata 注入 system prompt（轻），全文按需 read_file 加载。
"""

from openagentic.skills.manager import (
    SKILLS_DIR,
    Skill,
    SkillError,
    SkillNotFound,
    SkillsManager,
)

__all__ = ["SKILLS_DIR", "Skill", "SkillError", "SkillNotFound", "SkillsManager"]
