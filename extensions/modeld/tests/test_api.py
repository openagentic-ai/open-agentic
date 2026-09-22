"""modeld HTTP 接口契约。

核心是 /ensure 的准入判断：显存不够时必须明确拒绝（附占用者），
绝不尝试拉起——今天 27B 反复起不来就是因为没人做这一步。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.gpu import GpuState, GpuUser
from app.main import create_app
from app.xinference import ModelStatus

YAML = """
xinference:
  base_url: "http://127.0.0.1:9997"
  username: "admin"
  password: "pw"
  api_key: "k"
gpu:
  driver_overhead_mib: 459
models:
  - model_uid: "Qwen3.8-27B"
    model_name: "Qwen3.8-27B"
    gpu_memory_utilization: 0.95
    max_model_len: 32768
    max_num_seqs: 2
"""


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "modeld.yaml"
    p.write_text(YAML, encoding="utf-8")
    return load_config(p)


class _FakeClient:
    def __init__(self, status: ModelStatus):
        self._status = status
        self.launches: list[str] = []
        self.probe_calls = 0

    def probe(self, spec):
        self.probe_calls += 1
        return self._status

    def launch(self, spec):
        self.launches.append(spec.model_uid)
        return 200, "{}"


def _make(cfg, status, gpu_state):
    client = _FakeClient(status)
    app = create_app(cfg, client=client, gpu_state=lambda: gpu_state)
    return TestClient(app), client


IDLE = GpuState(total_mib=24564, used_mib=9, free_mib=24102, users=())
CONTENDED = GpuState(
    total_mib=24564,
    used_mib=8575,
    free_mib=15535,
    users=(GpuUser(pid=49260, name="VLLM::EngineCore", used_mib=8558),),
)


def test_healthz_ready(cfg):
    c, _ = _make(cfg, ModelStatus("ready"), IDLE)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["state"] == "ready"
    assert r.json()["usable"] is True


def test_healthz_loading_reports_reason(cfg):
    c, _ = _make(cfg, ModelStatus("loading", "实例正在加载"), IDLE)
    body = c.get("/healthz").json()
    assert body["state"] == "loading"
    assert body["detail"] == "实例正在加载"


def test_gpu_reports_users(cfg):
    c, _ = _make(cfg, ModelStatus("ready"), CONTENDED)
    body = c.get("/gpu").json()
    assert body["free_mib"] == 15535
    assert body["users"][0]["pid"] == 49260


def test_ensure_returns_ready_without_launching(cfg):
    c, client = _make(cfg, ModelStatus("ready"), IDLE)
    body = c.post("/ensure").json()
    assert body["state"] == "ready"
    assert body["action"] == "none"
    assert client.launches == []


def test_ensure_refuses_when_vram_insufficient(cfg):
    """2026-09-22 现场：被 reranker 占了 8.4G，必须明确拒绝且不尝试拉起。"""
    c, client = _make(cfg, ModelStatus("loading", "实例正在加载"), CONTENDED)
    r = c.post("/ensure")
    assert r.status_code == 409
    body = r.json()
    assert body["action"] == "refused"
    assert body["shortfall_mib"] > 0
    assert body["users"][0]["pid"] == 49260
    assert client.launches == []


def test_ensure_launches_when_room_available(cfg):
    c, client = _make(cfg, ModelStatus("down"), IDLE)
    body = c.post("/ensure").json()
    assert body["state"] == "launching"
    assert client.launches == ["Qwen3.8-27B"]


def test_healthz_caches_probe_within_ttl(cfg):
    """探测打的是真实补全、会占序列槽位——TTL 内不能重复打。"""
    c, client = _make(cfg, ModelStatus("ready"), IDLE)
    c.get("/healthz")
    c.get("/healthz")
    c.get("/healthz")
    assert client.probe_calls == 1


def test_ensure_reuses_cached_probe(cfg):
    c, client = _make(cfg, ModelStatus("ready"), IDLE)
    c.get("/healthz")
    c.post("/ensure")
    assert client.probe_calls == 1
