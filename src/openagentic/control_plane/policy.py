"""模块说明（中文）：`src/openagentic/control_plane/policy.py`。

分级策略——纯函数，无 IO、无状态、可独立单测。

契约：
- `gate_category(api_base, cfg)`：api_base 命中某个 tier 的端点 → 用该 tier 的 gate_category；
  否则回落 `llm`。**cfg 为 None（控制面未启用）一律回落 `llm`**——保证现有行为零变化。
- `escalation_target(cfg)`：本地不可用时的升级目标模型；未启用 → None。
"""

from __future__ import annotations

from openagentic.control_plane.config import ControlPlaneConfig
from openagentic.config import SETTINGS

DEFAULT_CATEGORY = "llm"


def gate_category(api_base: str | None, cfg: ControlPlaneConfig | None = None) -> str:
    """按后端端点选并发配额类别。

    本地推理后端（vLLM 序列槽位有限）走受限类别，云端维持原有配额。
    """
    if cfg is None or not api_base:
        return DEFAULT_CATEGORY
    for tier in cfg.tiers.values():
        for endpoint in tier.endpoints:
            if endpoint and endpoint in api_base:
                return tier.gate_category
    return DEFAULT_CATEGORY


def escalation_target(cfg: ControlPlaneConfig | None = None) -> str | None:
    """本地后端不可用时的升级目标模型 id；未配置升级返回 None。"""
    if cfg is None or not cfg.escalation.enabled:
        return None
    return cfg.escalation.target_model or SETTINGS.LITELLM_DEFAULT_MODEL
