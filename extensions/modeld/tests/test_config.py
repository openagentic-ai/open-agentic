"""modeld YAML 配置加载契约。

配置是守护进程的必需输入（不是可选开关），缺失/非法必须显式失败，
不能像控制面那样静默返回 None——否则守护进程会带病运行。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ModeldConfig, load_config


VALID = """
xinference:
  base_url: "http://127.0.0.1:9997"
  username: "admin"
  password: "pw"
  api_key: "k"

gpu:
  driver_overhead_mib: 459

probe:
  cache_ttl_sec: 5

models:
  - model_uid: "Qwen3.8-27B"
    model_name: "Qwen3.8-27B"
    model_engine: "vllm"
    gpu_memory_utilization: 0.95
    max_model_len: 32768
    max_num_seqs: 2
    enforce_eager: true
"""


@pytest.fixture
def cfg_file(tmp_path: Path) -> Path:
    p = tmp_path / "modeld.yaml"
    p.write_text(VALID, encoding="utf-8")
    return p


def test_loads_xinference_and_model(cfg_file):
    cfg = load_config(cfg_file)
    assert isinstance(cfg, ModeldConfig)
    assert cfg.xinference.base_url == "http://127.0.0.1:9997"
    assert cfg.gpu.driver_overhead_mib == 459
    assert cfg.probe.cache_ttl_sec == 5


def test_model_spec_fields(cfg_file):
    m = load_config(cfg_file).primary
    assert m.model_uid == "Qwen3.8-27B"
    assert m.gpu_memory_utilization == 0.95
    assert m.max_model_len == 32768
    assert m.max_num_seqs == 2
    assert m.enforce_eager is True


def test_launch_body_matches_xinference_api(cfg_file):
    """launch body 的字段名是踩过坑的（model_uid+model_name 格式，带 model_engine）。"""
    body = load_config(cfg_file).primary.launch_body()
    assert body["model_uid"] == "Qwen3.8-27B"
    assert body["model_name"] == "Qwen3.8-27B"
    assert body["model_engine"] == "vllm"
    assert body["gpu_memory_utilization"] == 0.95
    assert body["max_model_len"] == 32768
    assert body["max_num_seqs"] == 2
    assert body["enforce_eager"] is True


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_no_models_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("xinference:\n  base_url: x\nmodels: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)


def test_watch_defaults_to_disabled(tmp_path):
    """默认不启用守护——在共享 GPU 上自动拉起模型是策略决定，不该默认替用户做主。"""
    p = tmp_path / "m.yaml"
    p.write_text(VALID, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.watch.enabled is False
    assert cfg.watch.interval_sec > 0


def test_watch_parsed_from_yaml(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(VALID + "\nwatch:\n  enabled: true\n  interval_sec: 30\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.watch.enabled is True
    assert cfg.watch.interval_sec == 30
