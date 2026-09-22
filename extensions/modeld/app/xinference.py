"""模块说明（中文）：`app/xinference.py`。

Xinference 客户端——探测与拉起。零第三方依赖（urllib）。

探测方式是打一次 max_tokens=1 的最小补全：只有它才能回答"现在能不能用"。
`/v1/models` 里列出模型 ≠ 可用，加载中也会被列出。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

from app.config import ModelSpec, XinferenceConfig

State = Literal["ready", "loading", "down"]

LOADING_MARKERS = ("launching, not yet ready", "Model is loading")


@dataclass(frozen=True)
class ModelStatus:
    state: State
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.state == "ready"


def classify_probe(http_status: int | None, body: str) -> ModelStatus:
    """把一次探测的原始结果归类成三态。纯函数，可单测。"""
    if http_status is None:
        return ModelStatus("down", "连不上 Xinference")
    if http_status == 200:
        return ModelStatus("ready", "")
    if any(m in body for m in LOADING_MARKERS):
        return ModelStatus("loading", "实例正在加载")
    if http_status in (502, 503, 504):
        return ModelStatus("loading", f"服务暂不可用 HTTP {http_status}")
    return ModelStatus("down", f"HTTP {http_status}: {body[:200]}")


class XinferenceClient:
    def __init__(self, cfg: XinferenceConfig, launch_timeout_sec: float = 900.0):
        self.cfg = cfg
        self.launch_timeout_sec = launch_timeout_sec
        self._jwt: str | None = None

    # -- 内部 ----------------------------------------------------------

    def _post(self, path: str, body: dict, token: str, timeout: float) -> tuple[int, str]:
        req = urllib.request.Request(
            self.cfg.base_url + path,
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def jwt(self) -> str:
        """管理操作需要 JWT；API key 无权启停模型。"""
        if self._jwt:
            return self._jwt
        _, body = self._post(
            "/token",
            {"username": self.cfg.username, "password": self.cfg.password},
            token="",
            timeout=10.0,
        )
        self._jwt = json.loads(body).get("access_token", "")
        return self._jwt

    # -- 对外 ----------------------------------------------------------

    def probe(self, spec: ModelSpec) -> ModelStatus:
        """打一次最小补全，判断模型现在能不能用。"""
        status, body = self._post(
            "/v1/chat/completions",
            {
                "model": spec.model_uid,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
            token=self.cfg.api_key,
            timeout=60.0,
        )
        return classify_probe(status, body)

    def launch(self, spec: ModelSpec) -> tuple[int, str]:
        """拉起模型实例。返回 (http_status, body)。"""
        return self._post(
            "/v1/models",
            spec.launch_body(),
            token=self.jwt(),
            timeout=self.launch_timeout_sec,
        )
