"""模块说明（中文）：`src/openagentic/control_plane/jev.py`。

Jev 客户端——封闭选项判断（choice / score / noul），返回带 confidence 的完整概率分布。
一次调用可 fan-out 问一组问题。

与控制面其余部分同构：**环境变量激活**，未配置则 `build_jev()` 返回 None，
调用方回落到原有流程；失败同样返回 None，绝不抛给主链路。

零第三方依赖（urllib）+ sha256 缓存 + 成本账本（jsonl）。
接口抽象：`JEV_BASE_URL` 指向任何兼容端点即可，将来换端侧模型只改 env。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ENV_ENABLED = "OPENAGENTIC_JEV_ENABLED"
ENV_BASE_URL = "JEV_BASE_URL"
ENV_MODEL = "JEV_MODEL"
ENV_PROXY = "JEV_PROXY"
ENV_TIMEOUT = "JEV_TIMEOUT_SEC"

DEFAULT_BASE = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"


def jev_enabled() -> bool:
    return os.environ.get(ENV_ENABLED, "").strip().lower() in ("1", "true", "yes")


def _api_key() -> str:
    return (
        os.environ.get("JEV_API_KEY", "").strip()
        or os.environ.get("TYPESAFE_API_KEY", "").strip()
    )


def _default_cache_dir() -> Path:
    # src/openagentic/control_plane/jev.py -> 项目根
    return Path(__file__).resolve().parent.parent.parent.parent / "logs"


def build_jev(cache_dir: str | Path | None = None, opener: Any = None) -> "JevClient | None":
    """开着且有 key 才返回客户端，否则 None（调用方回落现有流程）。"""
    if not jev_enabled():
        return None
    key = _api_key()
    if not key:
        return None
    return JevClient(
        base=os.environ.get(ENV_BASE_URL, DEFAULT_BASE),
        key=key,
        model=os.environ.get(ENV_MODEL, DEFAULT_MODEL),
        proxy=os.environ.get(ENV_PROXY, ""),
        timeout=float(os.environ.get(ENV_TIMEOUT, "") or 30.0),
        cache_dir=cache_dir,
        opener=opener,
    )


def _digest(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


class JevClient:
    def __init__(
        self,
        base: str,
        key: str,
        model: str = DEFAULT_MODEL,
        proxy: str = "",
        timeout: float = 30.0,
        cache_dir: str | Path | None = None,
        opener: Any = None,
        max_retries: int = 2,
    ):
        self.base = base.rstrip("/")
        self.key = key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else _default_cache_dir()
        if opener is not None:
            self._opener = opener
        elif proxy:
            self._opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
        else:
            self._opener = urllib.request.build_opener()
        self._cache: dict[str, dict] | None = None

    # -- 持久化 ----------------------------------------------------------

    @property
    def cache_path(self) -> Path:
        return self.cache_dir / "jev_cache.jsonl"

    @property
    def log_path(self) -> Path:
        return self.cache_dir / "jev_log.jsonl"

    def _load_cache(self) -> dict[str, dict]:
        if self._cache is None:
            self._cache = {}
            try:
                with self.cache_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if rec.get("key"):
                            self._cache[rec["key"]] = rec.get("answers") or {}
            except FileNotFoundError:
                pass
        return self._cache

    def _write_cache(self, key: str, answers: dict) -> None:
        self._load_cache()[key] = answers
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), "key": key, "answers": answers}
        with self.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _log(self, rec: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), **rec}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # -- 调用 ------------------------------------------------------------

    def ask(self, state: dict, questions: dict, max_retries: int | None = None) -> dict | None:
        """一次 fan-out 调用问一组问题，返回 {qid: answer}；失败或未配置返回 None。"""
        if not self.key:
            return None

        payload = {"model": self.model, "state": state, "questions": questions}
        ck = _digest(payload)
        cached = self._load_cache().get(ck)
        if cached is not None:
            self._log({"cache": True, "questions": list(questions)})
            return cached

        retries = self.max_retries if max_retries is None else max_retries
        for attempt in range(retries):
            try:
                data = self._post(payload)
            except Exception as exc:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                self._log({"error": str(exc), "questions": list(questions)})
                return None

            answers = data.get("answers") or {}
            if not answers:
                self._log({"error": "empty answers", "questions": list(questions)})
                return None

            self._write_cache(ck, answers)
            self._log({
                "model": data.get("model", self.model),
                "usage": data.get("usage", {}),
                "questions": list(questions),
                "answers": answers,
            })
            return answers
        return None

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.base + "/v1/systemone",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.key,
            },
        )
        with self._opener.open(req, timeout=self.timeout) as r:
            return json.loads(r.read())
