"""分级策略纯函数契约：

1. 本地端点 → llm_local 类别（受限配额，对齐 vLLM 序列槽位）
2. 云端端点 → llm 类别（原有配额）
3. 控制面未启用（cfg=None）→ 一律 llm —— 向后兼容，现有行为零变化
4. api_base 为 None（云端原生 provider）→ llm
5. 升级目标从配置读取；未启用升级 → None
"""

from __future__ import annotations

import pytest

from openagentic.control_plane.config import (
    ControlPlaneConfig,
    EscalationConfig,
    TierConfig,
)
from openagentic.control_plane.policy import escalation_target, gate_category


@pytest.fixture
def cfg() -> ControlPlaneConfig:
    return ControlPlaneConfig(
        tiers={
            "local": TierConfig(
                gate_category="llm_local",
                concurrency=2,
                endpoints=("127.0.0.1:9997", "localhost:9997"),
            ),
            "cloud": TierConfig(gate_category="llm", concurrency=30, endpoints=()),
        },
        escalation=EscalationConfig(enabled=True, target_model="deepseek/deepseek-v4-flash"),
    )


def test_local_endpoint_maps_to_local_category(cfg):
    assert gate_category("http://127.0.0.1:9997/v1", cfg) == "llm_local"


def test_localhost_endpoint_maps_to_local_category(cfg):
    assert gate_category("http://localhost:9997/v1", cfg) == "llm_local"


def test_cloud_endpoint_maps_to_llm_category(cfg):
    assert gate_category("https://api.deepseek.com/v1", cfg) == "llm"


def test_no_config_falls_back_to_llm(cfg):
    """控制面未启用时，必须完全维持原行为。"""
    assert gate_category("http://127.0.0.1:9997/v1", None) == "llm"


def test_none_api_base_falls_back_to_llm(cfg):
    assert gate_category(None, cfg) == "llm"


def test_escalation_target_from_config(cfg):
    assert escalation_target(cfg) == "deepseek/deepseek-v4-flash"


def test_escalation_disabled_returns_none():
    c = ControlPlaneConfig(
        tiers={},
        escalation=EscalationConfig(enabled=False, target_model="x/y"),
    )
    assert escalation_target(c) is None


def test_escalation_none_config_returns_none():
    assert escalation_target(None) is None
