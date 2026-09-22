"""模块说明（中文）：`src/openagentic/control_plane/config.py`。

控制面配置——YAML 驱动，环境变量激活。

设计原则（遵循 #3 解耦第一）：
1. 环境变量激活：`OPENAGENTIC_CONTROL_PLANE_CONFIG` 未设 → 返回 None，控制面完全不启用
2. 失败隔离：文件缺失 / 非法 YAML / 结构不合法 → 返回 None，绝不影响主链路
3. 零业务依赖：只 import PyYAML + 标准库 + structlog，可独立单测
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger("openagentic.control_plane.config")

ENV_CONFIG_PATH = "OPENAGENTIC_CONTROL_PLANE_CONFIG"


@dataclass(frozen=True)
class TierConfig:
    """一个后端分层的策略：走哪个 gate 类别、配额多少、哪些端点算这一层。"""

    gate_category: str
    concurrency: int = 0
    endpoints: tuple[str, ...] = ()


@dataclass(frozen=True)
class EscalationConfig:
    """本地不可用时的升级目标。"""

    enabled: bool = False
    target_model: str = ""


@dataclass(frozen=True)
class ControlPlaneConfig:
    tiers: dict[str, TierConfig] = field(default_factory=dict)
    escalation: EscalationConfig = field(default_factory=EscalationConfig)


def load_control_plane_config(path: str | Path | None = None) -> ControlPlaneConfig | None:
    """加载控制面配置。未配置 / 不可用一律返回 None（调用方回落现有行为）。"""
    raw = str(path or os.getenv(ENV_CONFIG_PATH, "")).strip()
    if not raw:
        return None

    p = Path(raw)
    if not p.is_file():
        logger.warning("control_plane.config_missing", path=raw)
        return None

    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("control_plane.config_invalid", path=raw, error=str(e))
        return None

    if not isinstance(data, dict):
        logger.warning("control_plane.config_not_mapping", path=raw)
        return None

    try:
        return _parse(data)
    except Exception as e:
        logger.warning("control_plane.config_parse_failed", path=raw, error=str(e))
        return None


def _parse(data: dict) -> ControlPlaneConfig:
    tiers: dict[str, TierConfig] = {}
    for name, spec in (data.get("tiers") or {}).items():
        spec = spec or {}
        tiers[str(name)] = TierConfig(
            gate_category=str(spec.get("gate_category") or "llm"),
            concurrency=int(spec.get("concurrency") or 0),
            endpoints=tuple(str(e) for e in (spec.get("endpoints") or ())),
        )

    esc = data.get("escalation") or {}
    escalation = EscalationConfig(
        enabled=bool(esc.get("enabled", False)),
        target_model=str(esc.get("target_model") or ""),
    )
    return ControlPlaneConfig(tiers=tiers, escalation=escalation)
