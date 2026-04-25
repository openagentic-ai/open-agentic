"""模块说明（中文）：`src/openagentic/skills/loader.py`。

SKILL.md 解析器：抽取 YAML frontmatter + markdown 正文。

约定：
- 起首必须是 `---\\n...---\\n`，否则视为无效 skill
- frontmatter 至少要有 `name` 和 `description`
- `allowed-tools` 为可选 list[str]，缺失视为 None（不限制）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_SKILL_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


@dataclass
class ParsedSkill:
    """单个 SKILL.md 解析结果（不带运行时上下文，纯 IO 产物）。"""

    slug: str
    name: str
    description: str
    allowed_tools: list[str] | None
    body: str
    path: Path

    @property
    def metadata_one_line(self) -> str:
        """system prompt 注入用的一行 metadata（不含正文）。"""
        return f"- **{self.name}** (`{self.path}`): {self.description}"


class SkillParseError(ValueError):
    """SKILL.md 内容不合法（缺 frontmatter / 缺必填字段 / YAML 错）。"""


def is_valid_slug(slug: str) -> bool:
    """slug 必须 lowercase、kebab-case，与目录名规则一致。"""
    return bool(_SKILL_SLUG_RE.match(slug))


def parse_skill_md(path: Path) -> ParsedSkill:
    """读 SKILL.md 文件并返回结构化对象。

    异常：
      - FileNotFoundError：路径不存在
      - SkillParseError：frontmatter 格式错或必填字段缺失
    """
    if not path.is_file():
        raise FileNotFoundError(f"SKILL.md not found: {path}")

    raw = path.read_text(encoding="utf-8")
    match = _FM_RE.match(raw)
    if not match:
        raise SkillParseError(
            f"{path}: missing or malformed YAML frontmatter (expected starts with '---' block)"
        )

    front_text, body = match.group(1), match.group(2)
    try:
        front = yaml.safe_load(front_text) or {}
    except yaml.YAMLError as exc:
        raise SkillParseError(f"{path}: invalid YAML frontmatter: {exc}") from exc

    if not isinstance(front, dict):
        raise SkillParseError(f"{path}: frontmatter must be a mapping, got {type(front).__name__}")

    name = front.get("name")
    description = front.get("description")
    if not name or not isinstance(name, str):
        raise SkillParseError(f"{path}: frontmatter missing required string 'name'")
    if not description or not isinstance(description, str):
        raise SkillParseError(f"{path}: frontmatter missing required string 'description'")

    # slug 取目录名（即父目录），同时校验 frontmatter 的 name 与之匹配
    slug = path.parent.name
    if not is_valid_slug(slug):
        raise SkillParseError(f"{path}: invalid slug '{slug}' (must be lowercase kebab-case)")
    if name != slug:
        raise SkillParseError(
            f"{path}: frontmatter name '{name}' does not match directory '{slug}'"
        )

    allowed_tools_raw = front.get("allowed-tools")
    allowed_tools: list[str] | None = None
    if allowed_tools_raw is not None:
        if not isinstance(allowed_tools_raw, list) or not all(
            isinstance(x, str) for x in allowed_tools_raw
        ):
            raise SkillParseError(
                f"{path}: 'allowed-tools' must be a list of strings if present"
            )
        allowed_tools = list(allowed_tools_raw)

    return ParsedSkill(
        slug=slug,
        name=name,
        description=description.strip(),
        allowed_tools=allowed_tools,
        body=body,
        path=path,
    )


def discover_skills(root: Path) -> tuple[list[ParsedSkill], list[tuple[Path, str]]]:
    """扫描 root 下的所有 <slug>/SKILL.md。

    返回：
      - 成功解析的 ParsedSkill 列表（按 slug 排序）
      - 解析失败列表 [(path, error_msg)]，调用方可决定如何报告
    """
    skills: list[ParsedSkill] = []
    errors: list[tuple[Path, str]] = []

    if not root.is_dir():
        return skills, errors

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            skills.append(parse_skill_md(skill_md))
        except (SkillParseError, FileNotFoundError) as exc:
            errors.append((skill_md, str(exc)))

    return skills, errors
