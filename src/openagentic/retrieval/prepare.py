"""模块说明（中文）：`src/openagentic/retrieval/prepare.py`。

前置阶段——在 System-2 主循环之前把上下文备好。

    判断要不要检索 → 检索 → 判够不够 → 不够则补充上下文 → 拼文本注入 system

返回的字符串可直接当 `ConversationEngine(on_before_chat=...)` 用——
引擎层因此**零改动**（`on_before_chat` 本来就是「循环前返回文本注入 system」）。

向后兼容：`route_enabled=False` 时**仍然无条件检索**，与三处旧实现一致——
route 关闭不是「不检索」，而是「不判断，照旧检索」。

失败一律 fail-open：判定失败按「够」处理并照常注入，检索失败返回 None。
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog

from openagentic.control_plane.config import load_control_plane_config
from openagentic.control_plane.system1 import _UNSET, judge_sufficient, need_retrieval
from openagentic.retrieval import SOURCES, Chunk, retrieve

logger = structlog.get_logger("openagentic.retrieval.prepare")

_SOURCE_TITLES = {
    "episodic": "既往经验",
    "procedural": "可复用流程",
    "core": "核心记忆",
    "knowledge": "知识库",
}

_INSUFFICIENT_NOTE = (
    "⚠️ 以上检索结果可能不足以完整回答（标注：资料不足）。"
    "**不要编造**；需要更多信息时请调用工具，或直接向用户说明还缺什么。"
)


def _format_chunks(chunks: list[Chunk], *, insufficient: bool = False) -> str:
    lines = ["## 检索到的上下文"]
    if insufficient:
        lines.append(_INSUFFICIENT_NOTE)

    by_source: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_source.setdefault(c.source, []).append(c)

    for source, group in by_source.items():
        lines.append(f"\n### {_SOURCE_TITLES.get(source, source)}")
        for i, c in enumerate(group, 1):
            title = f" {c.title}" if c.title else ""
            lines.append(f"{i}.{title}")
            lines.append(f"   {c.text[:400]}")

    return "\n".join(lines)


async def prepare_context(
    query: str,
    *,
    sources: tuple[str, ...] = SOURCES,
    top_k: int = 3,
    memory: Any = None,
    route_enabled: bool | None = None,
    sufficiency_enabled: bool | None = None,
    max_rounds: int | None = None,
    jev: Any = _UNSET,
) -> str | None:
    """备好上下文文本；不需要检索或无命中时返回 None。

    三个开关默认从控制面配置读（`system1.route` / `system1.sufficiency`）；
    显式传 True/False 可覆盖——单测用得上，也方便临时试跑。
    """
    cfg = load_control_plane_config()
    if route_enabled is None:
        route_enabled = bool(cfg and cfg.system1.route.enabled)
    if sufficiency_enabled is None:
        sufficiency_enabled = bool(cfg and cfg.system1.sufficiency.enabled)
    if max_rounds is None:
        max_rounds = cfg.system1.sufficiency.max_rounds if cfg else 1
    if top_k == 3 and cfg is not None:
        top_k = cfg.system1.sufficiency.top_k
    if route_enabled:
        need = await need_retrieval(query, jev=jev)
        if need is False:
            return None

    chunks = await retrieve(query, sources=sources, top_k=top_k, memory=memory)
    if not chunks:
        return None
    if not sufficiency_enabled:
        return _format_chunks(chunks)

    text = _format_chunks(chunks)
    enough = await judge_sufficient(query, text, jev=jev)
    if enough is not False:  # None（判定失败）按「够」处理——fail-open
        return text

    # 补充上下文：放宽检索范围再试；仍不够则带标记返回，让 System-2 知道别编
    for _ in range(max(0, max_rounds)):
        wider = await retrieve(query, sources=sources, top_k=top_k * 4, memory=memory)
        if not wider:
            break
        chunks = wider
        text = _format_chunks(chunks)
        if await judge_sufficient(query, text, jev=jev) is not False:
            return text

    return _format_chunks(chunks, insufficient=True)


# --- 钩子合成 ---------------------------------------------------------

BeforeChatHook = Callable[[list[dict]], Awaitable[str | None]]


def compose_hooks(*hooks: BeforeChatHook | None) -> BeforeChatHook | None:
    """把多个 `on_before_chat` 合成一个：按顺序调用、非空结果拼接。

    失败隔离：某个钩子抛异常只记日志并跳过，不影响其余的。
    """
    active = [h for h in hooks if h is not None]
    if not active:
        return None
    if len(active) == 1:
        return active[0]

    async def composed(messages: list[dict]) -> str | None:
        parts: list[str] = []
        for h in active:
            try:
                out = await h(messages)
            except Exception:
                logger.warning("before_chat hook failed", exc_info=True)
                continue
            if out:
                parts.append(out)
        return "\n\n".join(parts) if parts else None

    return composed
