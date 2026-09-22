"""ensure_model 服务函数契约——从路由里抽出，供 HTTP 与守护循环共用。"""

from __future__ import annotations

import pytest

from app.config import load_config
from app.gpu import GpuState, GpuUser
from app.service import ensure_model
from app.xinference import ModelStatus

YAML = """
xinference:
  base_url: "http://127.0.0.1:9997"
  api_key: "k"
models:
  - model_uid: "Qwen3.8-27B"
    gpu_memory_utilization: 0.95
    max_num_seqs: 2
"""


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(YAML, encoding="utf-8")
    return load_config(p)


class _FakeClient:
    def __init__(self, status):
        self._status = status
        self.launches = []

    def probe(self, spec):
        return self._status

    def launch(self, spec):
        self.launches.append(spec.model_uid)
        return 200, "{}"


IDLE = GpuState(total_mib=24564, used_mib=9, free_mib=24102, users=())
CONTENDED = GpuState(
    total_mib=24564, used_mib=8575, free_mib=15535,
    users=(GpuUser(pid=49260, name="VLLM::EngineCore", used_mib=8558),),
)


def test_returns_ready_without_launching(cfg):
    client = _FakeClient(ModelStatus("ready"))
    r = ensure_model(cfg, client=client, gpu_state=lambda: IDLE)
    assert r.status_code == 200
    assert r.payload["action"] == "none"
    assert client.launches == []


def test_refuses_when_vram_insufficient(cfg):
    client = _FakeClient(ModelStatus("loading", "实例正在加载"))
    r = ensure_model(cfg, client=client, gpu_state=lambda: CONTENDED)
    assert r.status_code == 409
    assert r.payload["action"] == "refused"
    assert r.payload["shortfall_mib"] > 0
    assert client.launches == []


def test_launches_when_room_available(cfg):
    client = _FakeClient(ModelStatus("down"))
    r = ensure_model(cfg, client=client, gpu_state=lambda: IDLE)
    assert r.status_code == 200
    assert r.payload["action"] == "launched"
    assert client.launches == ["Qwen3.8-27B"]
