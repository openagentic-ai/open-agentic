"""模块说明（中文）：`app/main.py`。

modeld HTTP 接口。三个端点：

- `GET  /healthz`  模型现在能不能用（打一次最小补全判定）
- `GET  /gpu`      显存全貌 + 占用者（诊断用）
- `POST /ensure`   确保模型可用：够显存就拉起，不够就明确拒绝并说明被谁占了

依赖全部可注入（client / gpu_state），便于单测。
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import ModeldConfig
from app.gpu import check_capacity, query_state
from app.xinference import XinferenceClient


def _users_payload(g) -> list[dict]:
    return [{"pid": u.pid, "name": u.name, "used_mib": u.used_mib} for u in g.users]


def _cached_probe(client, spec, ttl_sec: float):
    """探测打的是真实补全、会占序列槽位（本地 vLLM 只有 2 个），TTL 内复用结果。"""
    last: dict = {"at": 0.0, "status": None}

    def probe():
        now = time.monotonic()
        cached = last["status"]
        if cached is not None and (now - last["at"]) < ttl_sec:
            return cached
        st = client.probe(spec)
        last["at"] = now
        last["status"] = st
        return st

    return probe


def create_app(cfg: ModeldConfig, *, client=None, gpu_state=None) -> FastAPI:
    client = client if client is not None else XinferenceClient(
        cfg.xinference, cfg.probe.launch_timeout_sec
    )
    gpu_state = gpu_state if gpu_state is not None else query_state
    spec = cfg.primary
    probe = _cached_probe(client, spec, cfg.probe.cache_ttl_sec)

    app = FastAPI(title="modeld", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        st = probe()
        return {
            "model_uid": spec.model_uid,
            "state": st.state,
            "usable": st.usable,
            "detail": st.detail,
        }

    @app.get("/gpu")
    def gpu() -> dict:
        g = gpu_state()
        return {
            "total_mib": g.total_mib,
            "used_mib": g.used_mib,
            "free_mib": g.free_mib,
            "users": _users_payload(g),
        }

    @app.post("/ensure")
    def ensure():
        st = probe()
        if st.usable:
            return {"model_uid": spec.model_uid, "state": "ready", "action": "none"}

        g = gpu_state()
        verdict = check_capacity(
            free_mib=g.free_mib,
            total_mib=g.total_mib,
            utilization=spec.gpu_memory_utilization,
            driver_overhead_mib=cfg.gpu.driver_overhead_mib,
        )
        if not verdict.ok:
            # 不够就直接说清楚被谁占了，不去撞 vLLM 那个语焉不详的报错
            return JSONResponse(
                status_code=409,
                content={
                    "model_uid": spec.model_uid,
                    "state": st.state,
                    "action": "refused",
                    "reason": verdict.reason(),
                    "required_mib": verdict.required_mib,
                    "free_mib": verdict.free_mib,
                    "shortfall_mib": verdict.shortfall_mib,
                    "users": _users_payload(g),
                },
            )

        http_status, body = client.launch(spec)
        if http_status >= 400:
            return JSONResponse(
                status_code=502,
                content={
                    "model_uid": spec.model_uid,
                    "state": "down",
                    "action": "launch_failed",
                    "http_status": http_status,
                    "detail": body[:500],
                },
            )
        return {
            "model_uid": spec.model_uid,
            "state": "launching",
            "action": "launched",
            "http_status": http_status,
        }

    return app
