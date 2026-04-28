"""模块说明（中文）：`src/openagentic/skills/router.py`。

Skills REST API —— 将 SkillsManager（文件级 SKILL.md）暴露为 HTTP 接口。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openagentic.skills.manager import SkillsManager, Skill, SkillNotFound, SkillError

router = APIRouter(prefix="/api/skills", tags=["skills"])

_mgr = SkillsManager()


class SkillResponse(BaseModel):
    """与前端 SkillsPage 兼容的 skill 视图。"""
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str | None = None
    category: str = "General"
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    source: str = "managed"
    allowed_tools: list[str] | None = None
    body: str | None = None  # 仅在 get 单条时返回

    @classmethod
    def from_skill(cls, s: Skill, include_body: bool = False) -> "SkillResponse":
        category = _guess_category(s.slug, s.description)
        tags = _guess_tags(s.slug, category, s.allowed_tools)
        return cls(
            id=s.slug,
            name=s.name,
            description=s.description,
            category=category,
            tags=tags,
            allowed_tools=s.allowed_tools,
            body=s.body if include_body else None,
        )


class SkillCreateRequest(BaseModel):
    slug: str = Field(..., max_length=64, pattern=r"^[a-z][a-z0-9-]*$",
                      description="skill 标识（lowercase kebab-case）")


def _guess_category(slug: str, description: str) -> str:
    """从 slug 前缀或描述中推测类别。"""
    mapping = {
        "file": "Productivity", "web": "Analysis", "image": "Media",
        "code": "Development", "data": "Analysis", "auto": "Automation",
        "safe": "Security", "pdf": "Utility", "ocr": "Utility",
        "notify": "Communication",
    }
    for prefix, cat in mapping.items():
        if slug.startswith(prefix):
            return cat
    desc_lower = description.lower()
    for kw, cat in mapping.items():
        if kw in desc_lower:
            return cat
    return "General"


def _guess_tags(slug: str, category: str, allowed_tools: list[str] | None) -> list[str]:
    """从 slug 和 allowed_tools 推测标签。"""
    tags: list[str] = []
    parts = slug.replace("_", "-").split("-")
    for p in parts:
        if p not in ("builtin", "clawhub") and len(p) > 1:
            tags.append(p)
    if allowed_tools:
        for t in allowed_tools:
            base = t.rsplit("_", 1)[0] if "_" in t else t
            if base not in tags:
                tags.append(base)
    return tags[:5]


@router.get("", response_model=list[SkillResponse])
def list_skills():
    """列出所有已安装 skill（按 slug 排序）。"""
    skills = _mgr.list_skills()
    # 播种内置 skill（首次启动），确保前端能看到默认集合
    if not skills:
        _mgr.ensure_seeded()
        skills = _mgr.list_skills()
    return [SkillResponse.from_skill(s) for s in skills]


@router.get("/{slug}", response_model=SkillResponse)
def get_skill(slug: str):
    """按 slug 获取单个 skill（含正文 body）。"""
    try:
        s = _mgr.get(slug)
    except SkillNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return SkillResponse.from_skill(s, include_body=True)


@router.post("", status_code=201, response_model=SkillResponse)
def create_skill(body: SkillCreateRequest):
    """创建 skill 模板（slug 必须唯一）。"""
    try:
        _mgr.create_template(body.slug)
    except SkillError as e:
        raise HTTPException(status_code=409, detail=str(e))
    s = _mgr.get(body.slug)
    return SkillResponse.from_skill(s, include_body=True)
