"""模块说明（中文）：`src/openagentic/skills/disclosure.py`。

渐进式技能加载（Progressive Disclosure）——对标 OpenAI/Anthropic 的三层加载策略：
  1. metadata-only：启动时只注入技能目录（名称+一句话描述），< 500 tokens
  2. SKILL.md 正文：仅当用户消息命中触发关键词时才完整加载
  3. 资源文件：关联的 scripts/templates 延迟到调用时才加载

设计：
  - 包装 SkillsManager，不改动现有解析/发现逻辑
  - 环境变量 OPENAGENTIC_SKILL_PROGRESSIVE=1 激活
  - 通过 ConversationEngine 的 on_before_chat callback 注入
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from openagentic.skills.manager import Skill, SkillsManager

# ── 环境变量 ──────────────────────────────────────────────
ENABLED = os.environ.get("OPENAGENTIC_SKILL_PROGRESSIVE", "0") == "1"

# 中文停用字——不参与匹配（在描述中高频出现但不携带语义）
_CN_STOP: set[str] = {
    "的", "是", "在", "和", "了", "有", "不", "这", "一", "个",
    "与", "或", "用", "可", "为", "以", "及", "等", "其", "所",
    "能", "要", "会", "让", "给", "对", "从", "到", "被", "把",
    "我", "你", "他", "她", "它", "们", "您", "该", "此", "各",
    "每", "都", "也", "就", "才", "便", "只", "但", "而", "且",
    "如", "若", "虽", "因", "故", "使", "将", "已", "正", "当",
    "中", "上", "下", "前", "后", "里", "外", "内", "间", "旁",
    "大", "小", "多", "少", "很", "更", "最", "较", "非", "还",
    "来", "去", "做", "说", "看", "想", "知", "见", "听", "写",
    "帮", "找", "问", "改", "加", "删", "查", "按", "通过",
    "时", "者", "处", "之", "本", "含", "同",
}


@dataclass
class SkillMetadata:
    """轻量 metadata，只含用于匹配和展示的最小信息集。"""

    slug: str
    name: str
    description: str
    # 触发关键词——英文词 ≥ 3 字符，中文特征字符（来自描述去停用后）
    triggers: list[str] = field(default_factory=list)


@dataclass
class LoadedSkill:
    """完整加载的 skill——metadata + 正文 + 资源路径。"""

    metadata: SkillMetadata
    body: str
    allowed_tools: list[str] | None
    path: str


class SkillDisclosure:
    """渐进式技能披露管理器。

    用法::

        mgr = SkillsManager()
        mgr.ensure_seeded()
        disclosure = SkillDisclosure(mgr)

        # 1. 启动时只注入 metadata（< 500 tokens）
        system_prompt_addition = disclosure.build_metadata_prompt()

        # 2. 收到用户消息时判断哪些 skill 相关
        triggered = disclosure.match(user_message)  # -> list[str]

        # 3. 只加载相关的 skill 正文
        for slug in triggered:
            skill = disclosure.load_full(slug)
    """

    def __init__(self, skills_manager: SkillsManager):
        self._mgr = skills_manager
        self._metadata_cache: list[SkillMetadata] | None = None
        # 已完整加载的 skill body 缓存
        self._loaded: dict[str, LoadedSkill] = {}

    # ── metadata ──────────────────────────────────────────

    def _ensure_metadata(self) -> list[SkillMetadata]:
        """扫描磁盘，构建 metadata 列表（缓存）。"""
        if self._metadata_cache is not None:
            return self._metadata_cache

        metas: list[SkillMetadata] = []
        for skill in self._mgr.list_skills():
            triggers = self._extract_triggers(skill)
            metas.append(SkillMetadata(
                slug=skill.slug,
                name=skill.name,
                description=skill.description,
                triggers=triggers,
            ))
        self._metadata_cache = metas
        return metas

    def _extract_triggers(self, skill: Skill) -> list[str]:
        """从 skill description 提取触发关键词。

        英文：≥ 3 字符的单词（如 review, commit, debug）。
        中文：去停用后的特征字符集，加上引号内拆分关键词。
        """
        triggers: list[str] = []

        # 英文词 ≥ 3 字符
        en_words = re.findall(r'[a-z]{3,}', skill.description.lower())
        triggers.extend(w for w in en_words if w not in {"the", "and", "for", "use", "when", "not", "are", "can", "all", "has", "too", "but"})

        # 引号内关键词，拆分 "/" 分隔的复合词
        quoted = re.findall(r'["""]([^"""]+)[""”]', skill.description)
        for q in quoted:
            q = q.strip()
            if len(q) < 2:
                continue
            if "/" in q and len(q) > 15:
                parts = [p.strip() for p in q.split("/") if len(p.strip()) >= 2]
                triggers.extend(parts)
            else:
                triggers.append(q)

        # 去停用后的中文字符集（用于单字匹配）
        cn_chars = set(re.findall(r'[\u4e00-\u9fff]', skill.description)) - _CN_STOP
        triggers.extend(cn_chars)  # 每个字一个触发项

        return triggers

    def build_metadata_prompt(self) -> str:
        """构建可注入 system prompt 的压缩技能目录。

        Returns:
            类似：
            ## 可用技能
            - code-review: 审阅代码改动，按反模式清单检查
            ...
            如果无技能则返回空字符串。
        """
        metas = self._ensure_metadata()
        if not metas:
            return ""

        lines = ["## 可用技能（说出触发词即可激活对应能力）"]
        for m in metas:
            desc = m.description[:100].replace("\n", " ")
            lines.append(f"- **{m.name}**: {desc}")
        return "\n".join(lines)

    @property
    def metadata_token_estimate(self) -> int:
        """估算 metadata prompt 的 token 数。

        中文密集文本约 2 字符/token，6 个内置 skill ≈ 300 tokens。
        """
        return len(self.build_metadata_prompt()) // 2

    # ── relevance ─────────────────────────────────────────

    def match(self, user_message: str) -> list[str]:
        """根据用户消息匹配相关 skill slug 列表。

        匹配策略：
          1. 英文词精确子串匹配（如用户说 "review" → code-review）
          2. slug 拆词匹配（"code-review" → "code"+"review"）
          3. 中文引号触发词子串匹配（如"审查代码"命中"审一下代码"的部分字）
          4. 中文单字命中率——触发词和用户消息之间的共享特征字数

        Returns:
            匹配的 slug 列表（按匹配质量排序）
        """
        if not user_message:
            return []

        msg_lower = user_message.lower()
        msg_cn_chars = set(re.findall(r'[\u4e00-\u9fff]', user_message)) - _CN_STOP
        metas = self._ensure_metadata()
        scored: list[tuple[int, str]] = []

        for m in metas:
            score = 0

            # 1. trigger 精确子串匹配
            for t in m.triggers:
                t_lower = t.lower()
                if t_lower in msg_lower:
                    # 单字中文触发词（特征字）权重较低
                    if len(t) == 1 and '\u4e00' <= t <= '\u9fff':
                        score += 2
                    elif len(t) >= 3:
                        score += 10
                    else:
                        score += 5

            # 2. slug 拆词匹配（双向）
            slug_parts = m.slug.replace("-", " ").split()
            msg_en_words = set(re.findall(r'[a-z]{3,}', msg_lower))
            for part in slug_parts:
                part_l = part.lower()
                if len(part_l) >= 3:
                    if part_l in msg_lower:
                        score += 8
                    # 反向：消息中的英文词包含 slug 词（如 "bug" ⊆ "debug"）
                    for mw in msg_en_words:
                        if part_l in mw or mw in part_l:
                            score += 6
                            break

            # 3. 中文特征字命中率
            #    从 trigger 列表中收集所有单字触发词
            trigger_cn_chars = {t for t in m.triggers if len(t) == 1 and '\u4e00' <= t <= '\u9fff'}
            #    计算共享特征字
            shared_chars = trigger_cn_chars & msg_cn_chars
            if len(shared_chars) >= 2:
                score += len(shared_chars) * 2

            # 4. 最低分阈值（至少一条强信号或两条中信号）
            if score >= 6:
                scored.append((score, m.slug))

        scored.sort(key=lambda x: -x[0])
        return [slug for _score, slug in scored]

    def is_relevant(self, slug: str, user_message: str) -> bool:
        """单 skill 快速判断是否与用户消息相关。"""
        return slug in self.match(user_message)

    # ── full load ──────────────────────────────────────────

    def load_full(self, slug: str) -> LoadedSkill | None:
        """按需加载完整 skill（metadata + 正文 + 资源）。"""
        if slug in self._loaded:
            return self._loaded[slug]

        try:
            skill = self._mgr.get(slug)
        except Exception:
            return None

        meta = None
        for m in self._ensure_metadata():
            if m.slug == slug:
                meta = m
                break
        if meta is None:
            meta = SkillMetadata(slug=skill.slug, name=skill.name, description=skill.description)

        loaded = LoadedSkill(
            metadata=meta,
            body=skill.body,
            allowed_tools=skill.allowed_tools,
            path=str(skill.path),
        )
        self._loaded[slug] = loaded
        return loaded

    def load_all_triggered(self, user_message: str) -> list[LoadedSkill]:
        """匹配 + 批量加载所有相关 skill。"""
        slugs = self.match(user_message)
        result: list[LoadedSkill] = []
        for slug in slugs:
            loaded = self.load_full(slug)
            if loaded:
                result.append(loaded)
        return result

    def build_triggered_prompt(self, user_message: str) -> str:
        """生成已触发 skill 的完整指令注入 prompt。"""
        loaded = self.load_all_triggered(user_message)
        if not loaded:
            return ""

        blocks = ["\n## 已激活技能（本次对话适用）\n"]
        for s in loaded:
            tools_hint = f"（可用工具：{', '.join(s.allowed_tools)}）" if s.allowed_tools else ""
            blocks.append(f"### {s.metadata.name} {tools_hint}\n{s.body}\n")
        return "\n".join(blocks)

    def clear_cache(self) -> None:
        """清空已加载缓存（用于会话结束或 skill 热更新）。"""
        self._loaded.clear()
        self._metadata_cache = None
