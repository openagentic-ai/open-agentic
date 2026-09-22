"""模块说明（中文）：`app/service.py`。

ensure 逻辑——从 HTTP 路由抽出，供 `/ensure` 端点与守护循环共用。

准入规则：模型已就绪 → 什么都不做；模型不可用 → 先算显存账，
够就拉起，不够就明确拒绝并说明被谁占了（不去撞 vLLM 那句语焉不详的报错）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import ModeldConfig, ModelSpec
from app.gpu import check_capacity, query_state
from app.xinference import XinferenceClient


@dataclass(frozen=True)
class EnsureResult:
    status_code: int
    payload: dict


def _users_payload(g) -> list[dict]:
    return [{"pid": u.pid, "name": u.name, "used_mib": u.used_mib} for u in g.users]


def ensure_model(
    cfg: ModeldConfig,
    *,
    client=None,
    gpu_state=None,
    probe=None,
    spec: ModelSpec | None = None,
) -> EnsureResult:
    client = client if client is not None else XinferenceClient(
        cfg.xinference, cfg.probe.launch_timeout_sec
    )
    gpu_state = gpu_state if gpu_state is not None else query_state
    spec = spec if spec is not None else cfg.primary
    # probe 可注入以便共用 TTL 缓存（见 main.create_app）
    probe = probe if probe is not None else (lambda: client.probe(spec))

    st = probe()
    if st.usable:
        return EnsureResult(200, {"model_uid": spec.model_uid, "state": "ready", "action": "none"})

    g = gpu_state()
    verdict = check_capacity(
        free_mib=g.free_mib,
        total_mib=g.total_mib,
        utilization=spec.gpu_memory_utilization,
        driver_overhead_mib=cfg.gpu.driver_overhead_mib,
    )
    if not verdict.ok:
        return EnsureResult(409, {
            "model_uid": spec.model_uid,
            "state": st.state,
            "action": "refused",
            "reason": verdict.reason(),
            "required_mib": verdict.required_mib,
            "free_mib": verdict.free_mib,
            "shortfall_mib": verdict.shortfall_mib,
            "users": _users_payload(g),
        })

    http_status, body = client.launch(spec)
    if http_status >= 400:
        return EnsureResult(502, {
            "model_uid": spec.model_uid,
            "state": "down",
            "action": "launch_failed",
            "http_status": http_status,
            "detail": body[:500],
        })
    return EnsureResult(200, {
        "model_uid": spec.model_uid,
        "state": "launching",
        "action": "launched",
        "http_status": http_status,
    })
