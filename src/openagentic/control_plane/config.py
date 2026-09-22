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
class VerifyConfig:
    """System-1 验证节点的策略。

    分级触发是核心：每次 Jev 判定要 +1 秒且计费，不能每条都过。
    """

    enabled: bool = False
    criteria: str = "回答必须切题、不得编造、与上下文一致"
    min_score: float = 0.7
    max_retries: int = 1
    trigger: str = "high_risk"   # high_risk | always | off
    high_risk_chars: int = 800


@dataclass(frozen=True)
class RouteConfig:
    """要不要检索的判定。加在请求最前面，开了等于每个请求 +1 次 Jev 调用。"""

    enabled: bool = False


@dataclass(frozen=True)
class SufficiencyConfig:
    """够不够的判定，以及判不够时怎么补充上下文。"""

    enabled: bool = False
    top_k: int = 3
    max_rounds: int = 1   # 补充轮数上限（每轮 = 一次检索 + 一次判定）


@dataclass(frozen=True)
class System1Config:
    verify: VerifyConfig = field(default_factory=VerifyConfig)
    route: RouteConfig = field(default_factory=RouteConfig)
    sufficiency: SufficiencyConfig = field(default_factory=SufficiencyConfig)


@dataclass(frozen=True)
class ControlPlaneConfig:
    tiers: dict[str, TierConfig] = field(default_factory=dict)
    escalation: EscalationConfig = field(default_factory=EscalationConfig)
    system1: System1Config = field(default_factory=System1Config)


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

    s1_raw = data.get("system1") or {}
    v_raw = s1_raw.get("verify") or {}
    verify = VerifyConfig(
        enabled=bool(v_raw.get("enabled", False)),
        criteria=str(v_raw.get("criteria") or VerifyConfig.criteria),
        min_score=float(v_raw.get("min_score", VerifyConfig.min_score)),
        max_retries=int(v_raw.get("max_retries", VerifyConfig.max_retries)),
        trigger=str(v_raw.get("trigger") or VerifyConfig.trigger),
        high_risk_chars=int(v_raw.get("high_risk_chars", VerifyConfig.high_risk_chars)),
    )

    r_raw = s1_raw.get("route") or {}
    route = RouteConfig(enabled=bool(r_raw.get("enabled", False)))

    suf_raw = s1_raw.get("sufficiency") or {}
    sufficiency = SufficiencyConfig(
        enabled=bool(suf_raw.get("enabled", False)),
        top_k=int(suf_raw.get("top_k", SufficiencyConfig.top_k)),
        max_rounds=int(suf_raw.get("max_rounds", SufficiencyConfig.max_rounds)),
    )

    esc = data.get("escalation") or {}
    escalation = EscalationConfig(
        enabled=bool(esc.get("enabled", False)),
        target_model=str(esc.get("target_model") or ""),
    )
    return ControlPlaneConfig(
        tiers=tiers,
        escalation=escalation,
        system1=System1Config(verify=verify, route=route, sufficiency=sufficiency),
    )
