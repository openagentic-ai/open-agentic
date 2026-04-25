"""模块说明（中文）：`src/openagentic/skills/manager.py`。

SkillsManager：扫描、查询、创建 skill；首次启动从内置目录播种。

设计：
- 用户态 skill 存 ~/.openagentic/skills/<slug>/
- 内置 skill 随仓库发布，首次启动复制到用户目录（不覆盖已有同名）
- list/get 全部走"扫描磁盘"——简单可靠，无需缓存（skill 数量 < 100）
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from openagentic.skills.loader import (
    ParsedSkill,
    SkillParseError,
    discover_skills,
    is_valid_slug,
    parse_skill_md,
)

SKILLS_DIR: Path = Path.home() / ".openagentic" / "skills"
_BUILTIN_DIR: Path = Path(__file__).parent / "builtin"
_SEED_MARKER_NAME = ".seeded"


class SkillError(Exception):
    """skill 操作通用错误。"""


class SkillNotFound(SkillError):
    """按 slug 查不到 skill。"""


@dataclass
class Skill:
    """对外暴露的 skill 视图（loader.ParsedSkill 的轻量包装）。"""

    slug: str
    name: str
    description: str
    allowed_tools: list[str] | None
    body: str
    path: Path

    @classmethod
    def from_parsed(cls, p: ParsedSkill) -> "Skill":
        return cls(
            slug=p.slug,
            name=p.name,
            description=p.description,
            allowed_tools=p.allowed_tools,
            body=p.body,
            path=p.path,
        )


class SkillsManager:
    """skill 生命周期入口。线程不安全；CLI 单进程使用足够。"""

    def __init__(self, root: Path | None = None):
        self.root = root or SKILLS_DIR

    # -- discovery ---------------------------------------------------------

    def ensure_seeded(self) -> list[str]:
        """首次启动复制内置 skill 到用户目录。

        返回新种入的 slug 列表（用于打印日志）。
        若 .seeded 标记已存在则不再复制；用户删除内置 skill 不会被自动恢复。
        """
        self.root.mkdir(parents=True, exist_ok=True)
        marker = self.root / _SEED_MARKER_NAME
        seeded: list[str] = []
        if marker.exists():
            return seeded
        if not _BUILTIN_DIR.is_dir():
            return seeded

        for src in sorted(_BUILTIN_DIR.iterdir()):
            if not src.is_dir():
                continue
            slug = src.name
            if not is_valid_slug(slug):
                continue
            dst = self.root / slug
            if dst.exists():
                continue  # 用户已有同名，不覆盖
            shutil.copytree(src, dst)
            seeded.append(slug)

        marker.write_text("seeded\n", encoding="utf-8")
        return seeded

    def list_skills(self) -> list[Skill]:
        """扫描磁盘返回当前所有 skill（按 slug 排序）。

        解析失败的 skill 会被静默跳过；如需调试用 list_with_errors()。
        """
        parsed, _errors = discover_skills(self.root)
        return [Skill.from_parsed(p) for p in parsed]

    def list_with_errors(self) -> tuple[list[Skill], list[tuple[Path, str]]]:
        """同 list_skills，但同时返回解析失败列表。"""
        parsed, errors = discover_skills(self.root)
        return [Skill.from_parsed(p) for p in parsed], errors

    def get(self, slug: str) -> Skill:
        """按 slug 加载单个 skill；找不到/解析失败抛 SkillNotFound。"""
        if not is_valid_slug(slug):
            raise SkillNotFound(f"invalid slug: {slug!r}")
        skill_md = self.root / slug / "SKILL.md"
        if not skill_md.is_file():
            raise SkillNotFound(f"skill not found: {slug}")
        try:
            return Skill.from_parsed(parse_skill_md(skill_md))
        except SkillParseError as exc:
            raise SkillNotFound(f"skill {slug} unreadable: {exc}") from exc

    # -- creation ----------------------------------------------------------

    def create_template(self, slug: str) -> Path:
        """在用户目录建一个模板 SKILL.md，返回路径。

        已存在则抛 SkillError 不覆盖。
        """
        if not is_valid_slug(slug):
            raise SkillError(
                f"invalid slug {slug!r}: use lowercase kebab-case (e.g. 'my-skill')"
            )
        dst_dir = self.root / slug
        if dst_dir.exists():
            raise SkillError(f"skill already exists: {dst_dir}")

        dst_dir.mkdir(parents=True)
        (dst_dir / "SKILL.md").write_text(_TEMPLATE.format(slug=slug), encoding="utf-8")
        return dst_dir / "SKILL.md"


_TEMPLATE = """---
name: {slug}
description: 一句话描述这个 skill 的用途，**包含触发条件**（如"当用户要求 X 时使用"），≤200 字。
allowed-tools: ["read_file", "write_file", "run_command"]
---

# {slug}

## 何时使用
- 列出明确的触发场景
- 越具体越好，避免与其他 skill 含义重叠

## 操作步骤
1. 第一步
2. 第二步
3. ...

## 注意事项
- 边界条件
- 安全约束（如修改前是否需要确认）

## 参考
- 可选：链接到其他文档或 reference/ 子目录文件
"""
