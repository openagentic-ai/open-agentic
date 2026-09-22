"""模块说明（中文）：`app/main.py`。

modeld HTTP 接口。三个端点：

- `GET  /healthz`  模型现在能不能用（打一次最小补全判定）
- `GET  /gpu`      显存全貌 + 占用者（诊断用）
- `POST /ensure`   确保模型可用：够显存就拉起，不够就明确拒绝并说明被谁占了

策略逻辑在 `app/service.py`，守护循环在 `app/watch.py`。依赖全部可注入，便于单测。
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import ModeldConfig
from app.gpu import query_state
from app.service import ensure_model
from app.watch import run_watch_loop
from app.xinference import XinferenceClient


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

    def _ensure():
        return ensure_model(cfg, client=client, gpu_state=gpu_state, probe=probe, spec=spec)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        stop = asyncio.Event()
        task = None
        if cfg.watch.enabled:
            task = asyncio.create_task(
                run_watch_loop(_ensure, cfg.watch.interval_sec, stop)
            )
        try:
            yield
        finally:
            if task is not None:
                stop.set()
                await task

    app = FastAPI(title="modeld", version="0.2.0", lifespan=lifespan)

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
            "users": [{"pid": u.pid, "name": u.name, "used_mib": u.used_mib} for u in g.users],
        }

    @app.post("/ensure")
    def ensure():
        r = _ensure()
        return JSONResponse(status_code=r.status_code, content=r.payload)

    return app
