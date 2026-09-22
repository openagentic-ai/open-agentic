"""控制面 YAML 配置加载契约：

1. env 未设 → 返回 None（控制面整体不启用，现有行为不变）
2. env 指向不存在的文件 → 返回 None（失败隔离，不影响主链路）
3. 加载 YAML → 解析出 tiers / escalation
4. 非法 YAML → 返回 None，不抛
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openagentic.control_plane import load_control_plane_config
from openagentic.control_plane.config import ControlPlaneConfig, TierConfig


MINIMAL_YAML = """
version: 1
tiers:
  local:
    gate_category: llm_local
    concurrency: 2
    endpoints:
      - "127.0.0.1:9997"
      - "localhost:9997"
  cloud:
    gate_category: llm
    concurrency: 30
escalation:
  enabled: true
  target_model: "deepseek/deepseek-v4-flash"
"""


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    p = tmp_path / "control_plane.yaml"
    p.write_text(MINIMAL_YAML, encoding="utf-8")
    return p


def test_disabled_when_env_unset(monkeypatch, yaml_file):
    """env 未设 → None，控制面完全不启用。"""
    monkeypatch.delenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", raising=False)
    assert load_control_plane_config() is None


def test_disabled_when_file_missing(monkeypatch, tmp_path):
    """env 指向不存在的文件 → None（失败隔离，不能让主链路挂）。"""
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(tmp_path / "nope.yaml"))
    assert load_control_plane_config() is None


def test_disabled_on_invalid_yaml(monkeypatch, tmp_path):
    """非法 YAML → None，不抛。"""
    bad = tmp_path / "bad.yaml"
    bad.write_text("tiers: [unclosed\n", encoding="utf-8")
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(bad))
    assert load_control_plane_config() is None


def test_loads_tiers_and_escalation(monkeypatch, yaml_file):
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(yaml_file))
    cfg = load_control_plane_config()
    assert isinstance(cfg, ControlPlaneConfig)

    assert set(cfg.tiers) == {"local", "cloud"}
    local = cfg.tiers["local"]
    assert isinstance(local, TierConfig)
    assert local.gate_category == "llm_local"
    assert local.concurrency == 2
    assert "127.0.0.1:9997" in local.endpoints

    assert cfg.escalation.enabled is True
    assert cfg.escalation.target_model == "deepseek/deepseek-v4-flash"


# --- system1 配置段 ---------------------------------------------------

SYSTEM1_YAML = """
version: 1
tiers:
  local:
    gate_category: llm_local
    concurrency: 2
    endpoints: ["127.0.0.1:9997"]
system1:
  verify:
    enabled: true
    criteria: "必须引用来源"
    min_score: 0.8
    max_retries: 2
    trigger: always
    high_risk_chars: 500
"""


def test_system1_defaults_to_disabled(monkeypatch, yaml_file):
    """不配 system1 段 → 验证默认关闭，引擎行为与从前一致。"""
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(yaml_file))
    cfg = load_control_plane_config()
    assert cfg.system1.verify.enabled is False


def test_system1_parsed(monkeypatch, tmp_path):
    p = tmp_path / "cp.yaml"
    p.write_text(SYSTEM1_YAML, encoding="utf-8")
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(p))
    cfg = load_control_plane_config()
    v = cfg.system1.verify
    assert v.enabled is True
    assert v.criteria == "必须引用来源"
    assert v.min_score == 0.8
    assert v.max_retries == 2
    assert v.trigger == "always"
    assert v.high_risk_chars == 500
