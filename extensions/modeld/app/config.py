"""模块说明（中文）：`app/config.py`。

modeld 的 YAML 配置。配置是守护进程的必需输入，缺失/非法显式失败——
不像控制面那样静默降级，否则守护进程会带病运行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class XinferenceConfig:
    base_url: str
    username: str = "admin"
    password: str = ""
    api_key: str = ""


@dataclass(frozen=True)
class GpuConfig:
    driver_overhead_mib: int = 459


@dataclass(frozen=True)
class ProbeConfig:
    cache_ttl_sec: float = 5.0
    launch_timeout_sec: float = 900.0


@dataclass(frozen=True)
class WatchConfig:
    """守护循环：定期确保模型可用。

    默认关闭——在共享 GPU 上自动拉起模型是策略决定，不该默认替用户做主。
    """

    enabled: bool = False
    interval_sec: float = 60.0


@dataclass(frozen=True)
class ModelSpec:
    model_uid: str
    model_name: str
    model_engine: str = "vllm"
    gpu_memory_utilization: float = 0.95
    max_model_len: int = 32768
    max_num_seqs: int = 2
    enforce_eager: bool = True

    def launch_body(self) -> dict:
        """Xinference launch 请求体。

        字段名是踩过坑的：必须用 model_uid + model_name（用 model_format/quantization 会 400），
        且必须带 model_engine，否则报 "Please specify the model_engine field"。
        """
        return {
            "model_uid": self.model_uid,
            "model_name": self.model_name,
            "model_engine": self.model_engine,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "max_model_len": self.max_model_len,
            "max_num_seqs": self.max_num_seqs,
            "enforce_eager": self.enforce_eager,
        }


@dataclass(frozen=True)
class ModeldConfig:
    xinference: XinferenceConfig
    models: tuple[ModelSpec, ...] = field(default_factory=tuple)
    gpu: GpuConfig = field(default_factory=GpuConfig)
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    watch: WatchConfig = field(default_factory=WatchConfig)

    @property
    def primary(self) -> ModelSpec:
        if not self.models:
            raise ValueError("配置里没有任何模型")
        return self.models[0]


def load_config(path: str | Path) -> ModeldConfig:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"配置文件不存在：{p}")

    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"配置根节点必须是映射：{p}")

    xi = data.get("xinference") or {}
    if not xi.get("base_url"):
        raise ValueError("配置缺少 xinference.base_url")

    models = tuple(
        ModelSpec(
            model_uid=str(m["model_uid"]),
            model_name=str(m.get("model_name") or m["model_uid"]),
            model_engine=str(m.get("model_engine") or "vllm"),
            gpu_memory_utilization=float(m.get("gpu_memory_utilization", 0.95)),
            max_model_len=int(m.get("max_model_len", 32768)),
            max_num_seqs=int(m.get("max_num_seqs", 2)),
            enforce_eager=bool(m.get("enforce_eager", True)),
        )
        for m in (data.get("models") or [])
    )
    if not models:
        raise ValueError("配置里没有任何模型")

    gpu_raw = data.get("gpu") or {}
    probe_raw = data.get("probe") or {}
    watch_raw = data.get("watch") or {}

    return ModeldConfig(
        xinference=XinferenceConfig(
            base_url=str(xi["base_url"]).rstrip("/"),
            username=str(xi.get("username") or "admin"),
            password=str(xi.get("password") or ""),
            api_key=str(xi.get("api_key") or ""),
        ),
        models=models,
        gpu=GpuConfig(driver_overhead_mib=int(gpu_raw.get("driver_overhead_mib", 459))),
        probe=ProbeConfig(
            cache_ttl_sec=float(probe_raw.get("cache_ttl_sec", 5.0)),
            launch_timeout_sec=float(probe_raw.get("launch_timeout_sec", 900.0)),
        ),
        watch=WatchConfig(
            enabled=bool(watch_raw.get("enabled", False)),
            interval_sec=float(watch_raw.get("interval_sec", 60.0)),
        ),
    )
