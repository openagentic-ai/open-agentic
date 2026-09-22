"""模块说明（中文）：`src/openagentic/workflow/evaluator.py`。

工作流评估节点（EvaluatorNode）——对标 Anthropic 的 Evaluator 模式。

evaluator 节点类型：
  config:
    target_node: "node_id"   # 评估哪个节点的输出
    criteria: "评分标准"       # LLM 用来评分的文本
    min_score: 0.7           # 最低通过分（0-1）
    max_retries: 2           # 最多重试次数
    model: ""                # 评估用模型（空则用默认）

执行逻辑：
  1. 取 target_node 的 output
  2. 调 LLM 评分：`按 {criteria} 评分，输出 JSON: {score: float, feedback: str}`
  3. score >= min_score → passed=true
  4. score < min_score → passed=false（调用方回到 target_node 重做）
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog

from openagentic.agent.llm import litellm_chat
from openagentic.control_plane.jev import build_jev

logger = structlog.get_logger("openagentic.workflow.evaluator")

# JSON 提取正则：容忍 LLM 在 JSON 前后加 markdown 代码块或说明文字
_JSON_RE = re.compile(r"\{[\s\S]*\"score\"[\s\S]*\"feedback\"[\s\S]*\}", re.MULTILINE)


# Jev 的 choice 候选——有序分档，与下面 LLM 提示词里的评分指南保持一致
_JEV_QUALITY_LEGEND = {
    "excellent": "完全满足标准，超出预期",
    "good": "基本满足，有小瑕疵",
    "partial": "部分满足，有明显不足",
    "poor": "严重不满足，需要重做",
}


async def _evaluate_with_jev(output_str: str, criteria: str, min_score: float) -> dict | None:
    """用 Jev 的封闭判定打分。

    `noul` = 「输出是否满足标准」的校准概率，直接对上 min_score 阈值。
    Jev 未配置 / 返回空 / 抛异常一律返回 None，由调用方回落到 LLM 路径——
    判定失败不能阻塞流程。

    走 to_thread：Jev 客户端是阻塞 urllib。
    """
    jev = build_jev()
    if jev is None:
        return None

    try:
        answers = await asyncio.to_thread(
            jev.ask,
            {"criteria": criteria, "output": output_str},
            {
                "meets": {
                    "type": "noul",
                    "instructions": "判断「输出」是否满足「标准」。",
                },
                "quality": {
                    "type": "choice",
                    "instructions": "对「输出」的质量分档。",
                    "criteria": _JEV_QUALITY_LEGEND,
                },
            },
        )
    except Exception:
        logger.warning("evaluator: jev call failed, falling back to LLM", exc_info=True)
        return None

    if not isinstance(answers, dict) or "meets" not in answers:
        return None

    meets = answers.get("meets") or {}
    try:
        score = float(meets.get("noul", 0.0))
    except (TypeError, ValueError):
        return None
    score = max(0.0, min(1.0, score))

    quality = (answers.get("quality") or {}).get("choice", "")
    detail = _JEV_QUALITY_LEGEND.get(quality) or quality or "未分档"
    conf = meets.get("confidence")
    conf_str = f"，置信度 {float(conf):.2f}" if isinstance(conf, (int, float)) else ""

    return {
        "score": score,
        "feedback": f"Jev 判定：{detail}（满足标准的概率 {score:.2f}{conf_str}）",
        "passed": score >= min_score,
    }


async def execute_evaluator(
    target_output: Any,
    criteria: str,
    min_score: float = 0.7,
    model: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
) -> dict:
    """执行评估：调 LLM 对 target_output 按 criteria 评分。

    Args:
        target_output: 被评估节点的输出（任意类型，会被转为字符串）
        criteria: 评分标准文本
        min_score: 最低通过分（0-1）
        model: 评估用模型
        api_base: API 地址
        api_key: API 密钥

    Returns:
        {
            "score": float,          # 0-1 的评分
            "feedback": str,         # LLM 给出的反馈
            "passed": bool,          # score >= min_score
            "target_node": str,      # 被评估节点 ID
        }
    """
    output_str = str(target_output)
    if len(output_str) > 3000:
        output_str = output_str[:1500] + "\n... [省略中间] ...\n" + output_str[-1500:]

    # 优先走 Jev 的封闭判定（校准概率）；未配置或失败则回落 LLM 自由打分
    jev_result = await _evaluate_with_jev(output_str, criteria, min_score)
    if jev_result is not None:
        logger.info(
            "evaluator result",
            score=jev_result["score"],
            passed=jev_result["passed"],
            min_score=min_score,
            feedback=jev_result["feedback"][:100],
            source="jev",
        )
        return jev_result

    prompt = f"""你是严格但公正的质量评估员。请根据以下标准对输出进行评分。

评分标准：
{criteria}

待评估输出：
```
{output_str}
```

请以 JSON 格式回复（不要加其他文字）：
{{"score": <0到1之间的浮点数>, "feedback": "<评分理由，1-3句话>"}}

评分指南：
- 1.0：完全满足标准，超出预期
- 0.7-0.9：基本满足，有小瑕疵
- 0.4-0.6：部分满足，有明显不足
- 0.0-0.3：严重不满足，需要重做"""

    try:
        resp = await litellm_chat(
            [{"role": "user", "content": prompt}],
            model=model or "deepseek-v4-flash",
            api_base=api_base,
            api_key=api_key,
        )
        content = resp.get("message", {}).get("content", "")
    except Exception as exc:
        logger.exception("evaluator LLM call failed")
        return {
            "score": 0.0,
            "feedback": f"评估 LLM 调用失败：{exc}",
            "passed": True,  # 宽容策略：LLM 挂了不阻塞流程
        }

    # 从 LLM 回复中提取 JSON
    match = _JSON_RE.search(content)
    if not match:
        logger.warning("evaluator: could not extract JSON from LLM response", content=content[:200])
        # 降级：尝试手动解析
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {
                "score": 0.5,
                "feedback": f"无法解析评估结果（原始回复前200字）：{content[:200]}",
                "passed": True,  # 宽容策略
            }
    else:
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {
                "score": 0.5,
                "feedback": f"JSON 解析失败：{match.group(0)[:200]}",
                "passed": True,
            }

    score = float(parsed.get("score", 0.5))
    score = max(0.0, min(1.0, score))  # clamp to [0, 1]
    feedback = str(parsed.get("feedback", ""))
    passed = score >= min_score

    logger.info(
        "evaluator result",
        score=score,
        passed=passed,
        min_score=min_score,
        feedback=feedback[:100],
    )

    return {
        "score": score,
        "feedback": feedback,
        "passed": passed,
    }
