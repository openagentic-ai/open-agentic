"""模块说明（中文）：`src/openagentic/control_plane/system1.py`。

System-1 门面——RLCD 判定模型（Jev）在循环里的三个介入点。

System-1 = RLCD 训练的非自回归判定模型：**只做封闭选项判断、给校准概率、不生成文本**。
所以 `feedback` 必须从 `choice` 标签**合成**，不能让模型写——这是 RLCD 的硬约束。

三个判定各自独立开关：

| 函数 | 问题类型 | 用途 | 默认 |
|---|---|---|---|
| `verify_output` | `noul` + `choice` | 验证/打分 | 开 |
| `route_message` | `choice` | 判断/路由 | 关（多一次调用 = +1s） |
| `judge_sufficient` | `noul` | 信息够不够 | 关（引擎层暂无检索） |

Jev 未配置 / 返回空 / 抛异常一律返回 None，调用方回落原有流程——
**判定失败绝不阻塞主流程**。

本模块只做判定，不做编排；编排在 `agent/engine.py` 的 `on_verify` 钩子里。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog

from openagentic.control_plane.config import ControlPlaneConfig, load_control_plane_config
from openagentic.control_plane.jev import build_jev

logger = structlog.get_logger("openagentic.control_plane.system1")

# Jev 的 choice 候选——有序分档
_QUALITY_LEGEND = {
    "excellent": "完全满足标准，超出预期",
    "good": "基本满足，有小瑕疵",
    "partial": "部分满足，有明显不足",
    "poor": "严重不满足，需要重做",
}

SUFFICIENT_THRESHOLD = 0.5

# 哨兵：区分「没传（用默认客户端）」与「显式传 None（判定器不可用）」
# 用 None 兼表两义会让 "Jev 不可用" 退化成 "去建一个真客户端"。
_UNSET: Any = object()


@dataclass(frozen=True)
class VerifyVerdict:
    passed: bool
    score: float
    feedback: str           # 给人看的判定说明
    feedback_prompt: str    # 回注给 System-2 的提示行；通过时为空


# --- 分级触发（纯函数）------------------------------------------------

def should_verify(
    content: str,
    *,
    had_tool_calls: bool,
    trigger: str = "high_risk",
    high_risk_chars: int = 800,
) -> bool:
    """按风险决定这次返回要不要过 System-1。

    每次判定要 +1 秒且计费，不能每条都过。风险信号：
    本轮动过工具（不可逆）、输出偏长（更可能跑偏）。
    """
    if trigger == "off":
        return False
    if trigger == "always":
        return True
    return bool(had_tool_calls) or len(content) > high_risk_chars


# --- 内部 -------------------------------------------------------------

async def _ask(state: dict, questions: dict, jev: Any) -> dict | None:
    """统一入口：Jev 阻塞调用走线程；任何失败返回 None。"""
    client = build_jev() if jev is _UNSET else jev
    if client is None:
        return None
    try:
        return await asyncio.to_thread(client.ask, state, questions)
    except Exception:
        logger.warning("system1: jev call failed, falling back", exc_info=True)
        return None


# --- 判定一：验证/打分 -------------------------------------------------

async def verify_output(
    output: str,
    criteria: str,
    min_score: float = 0.7,
    *,
    jev: Any = _UNSET,
) -> VerifyVerdict | None:
    """判断输出是否达标。`noul` = 满足标准的校准概率，直接对上 min_score。"""
    answers = await _ask(
        {"criteria": criteria, "output": output},
        {
            "meets": {"type": "noul", "instructions": "判断「输出」是否满足「标准」。"},
            "quality": {
                "type": "choice",
                "instructions": "对「输出」的质量分档。",
                "criteria": _QUALITY_LEGEND,
            },
        },
        jev,
    )
    if not isinstance(answers, dict) or "meets" not in answers:
        return None

    meets = answers.get("meets") or {}
    try:
        score = float(meets.get("noul", 0.0))
    except (TypeError, ValueError):
        return None
    score = max(0.0, min(1.0, score))

    quality = (answers.get("quality") or {}).get("choice", "")
    detail = _QUALITY_LEGEND.get(quality) or quality or "未分档"
    conf = meets.get("confidence")
    conf_str = f"，置信度 {float(conf):.2f}" if isinstance(conf, (int, float)) else ""

    passed = score >= min_score
    feedback = f"Jev 判定：{detail}（满足标准的概率 {score:.2f}{conf_str}）"

    prompt = ""
    if not passed:
        prompt = (
            "上一次的回答未通过校验，请重做。\n"
            f"校验标准：{criteria}\n"
            f"判定结果：{detail}（满足概率 {score:.2f}{conf_str}）\n"
            "请针对上述不足重新作答，不要重复上一次的说法。"
        )

    return VerifyVerdict(
        passed=passed, score=score, feedback=feedback, feedback_prompt=prompt
    )


# --- 判定二：路由 -----------------------------------------------------

async def route_message(text: str, *, jev: Any = _UNSET) -> str | None:
    """判断该由谁处理：direct（直接答）/ cloud（重推理）/ local（要检索与工具）。"""
    answers = await _ask(
        {"message": text},
        {
            "route": {
                "type": "choice",
                "instructions": "判断这条消息该由谁处理。",
                "criteria": {
                    "direct": "简单闲聊或可直接回答，无需检索与工具",
                    "cloud": "需要深度推理或较长生成，交给云端大模型",
                    "local": "需要检索资料或调用工具，交给本地模型与工具链",
                },
            }
        },
        jev,
    )
    if not isinstance(answers, dict):
        return None
    route = (answers.get("route") or {}).get("choice")
    return str(route) if route else None


# --- 判定三：信息够不够 -----------------------------------------------

async def judge_sufficient(query: str, context: str, *, jev: Any = _UNSET) -> bool | None:
    """检索回来的上下文是否足以回答问题。"""
    answers = await _ask(
        {"query": query, "context": context},
        {"enough": {"type": "noul", "instructions": "「context」是否足以回答「query」？"}},
        jev,
    )
    if not isinstance(answers, dict) or "enough" not in answers:
        return None
    val = (answers.get("enough") or {}).get("noul")
    if not isinstance(val, (int, float)):
        return None
    return float(val) >= SUFFICIENT_THRESHOLD


# --- 激活助手 ---------------------------------------------------------

def build_verify_hook(cfg: ControlPlaneConfig | None = _UNSET):
    """按控制面配置造一个可直接传给 `ConversationEngine(on_verify=...)` 的回调。

    未配置控制面 / `system1.verify.enabled` 为 false → 返回 None，
    引擎行为与从前**完全一致**。这是「不配置就不启用」的解耦约定。

    注意 `cfg` 用哨兵而非 `None` 作默认：`None` 兼表「没传」与「显式无配置」
    会让后者退化成「去读默认配置」，行为随部署环境漂移。
    """
    cfg = load_control_plane_config() if cfg is _UNSET else cfg
    if cfg is None:
        return None

    v = cfg.system1.verify
    if not v.enabled:
        return None

    async def on_verify(content: str, messages: list[dict]) -> VerifyVerdict | None:
        had_tool_calls = any(m.get("role") == "tool" for m in messages)
        if not should_verify(
            content,
            had_tool_calls=had_tool_calls,
            trigger=v.trigger,
            high_risk_chars=v.high_risk_chars,
        ):
            return None
        return await verify_output(content, v.criteria, v.min_score)

    return on_verify
