"""模块说明（中文）：`src/openagentic/concurrency/config.py`。

并发底座的配置——全部走环境变量，未配置使用 100 量级默认值。

为什么不复用 openagentic.config.SETTINGS？
底座必须零业务依赖（#3 解耦第一原则·规则 4），SETTINGS 拉起会带 DB/auth/litellm，
此处只读裸 ENV，保持底座可独立单测、可独立部署、加载失败不影响应用主链路。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class CategoryConfig:
    """单个类别的并发配额 + 可选令牌桶限流。"""

    concurrency: int                # 同类别最大并发
    rate_per_sec: float | None = None  # 令牌桶补充速率（None 表示不限速）
    burst: int | None = None           # 令牌桶容量（None 表示等于 concurrency）


@dataclass(frozen=True)
class GateConfig:
    """并发底座总配置。

    100 量级单机默认（按用户要求）：
    - 全局并发 100：单机部署的安全水位
    - 排队上限 200：突发短峰时不立即拒，长峰时拒掉防雪崩
    - 默认 timeout 180s：与现有飞书层 wait_for 对齐
    - LLM 30 并发 + 50/s 令牌桶：保护 provider QPS
    - subprocess 10 并发：保护机器 CPU/IO
    - io 50 并发：文件 I/O 异步化后的水位
    """

    global_concurrency: int = 100
    max_queued: int = 200
    default_timeout: float = 180.0
    categories: dict[str, CategoryConfig] = field(default_factory=lambda: {
        "default": CategoryConfig(concurrency=100),
        "llm": CategoryConfig(concurrency=30, rate_per_sec=50.0, burst=30),
        "subprocess": CategoryConfig(concurrency=10),
        "io": CategoryConfig(concurrency=50),
    })

    @classmethod
    def from_env(cls) -> "GateConfig":
        """从环境变量加载配置，未配置项走默认值。

        环境变量清单：
            OPENAGENTIC_GATE_GLOBAL_CONCURRENCY     全局并发上限
            OPENAGENTIC_GATE_MAX_QUEUED             排队上限
            OPENAGENTIC_GATE_DEFAULT_TIMEOUT        默认超时（秒）
            OPENAGENTIC_GATE_LLM_CONCURRENCY        LLM 类别并发
            OPENAGENTIC_GATE_LLM_RATE               LLM 类别令牌桶补充速率
            OPENAGENTIC_GATE_SUBPROCESS_CONCURRENCY 子进程类别并发
            OPENAGENTIC_GATE_IO_CONCURRENCY         文件 I/O 类别并发
        """
        defaults = cls()
        return cls(
            global_concurrency=_env_int(
                "OPENAGENTIC_GATE_GLOBAL_CONCURRENCY", defaults.global_concurrency
            ),
            max_queued=_env_int(
                "OPENAGENTIC_GATE_MAX_QUEUED", defaults.max_queued
            ),
            default_timeout=_env_float(
                "OPENAGENTIC_GATE_DEFAULT_TIMEOUT", defaults.default_timeout
            ),
            categories={
                "default": defaults.categories["default"],
                "llm": CategoryConfig(
                    concurrency=_env_int(
                        "OPENAGENTIC_GATE_LLM_CONCURRENCY",
                        defaults.categories["llm"].concurrency,
                    ),
                    rate_per_sec=_env_float(
                        "OPENAGENTIC_GATE_LLM_RATE",
                        defaults.categories["llm"].rate_per_sec or 0.0,
                    ) or None,
                    burst=defaults.categories["llm"].burst,
                ),
                "subprocess": CategoryConfig(
                    concurrency=_env_int(
                        "OPENAGENTIC_GATE_SUBPROCESS_CONCURRENCY",
                        defaults.categories["subprocess"].concurrency,
                    ),
                ),
                "io": CategoryConfig(
                    concurrency=_env_int(
                        "OPENAGENTIC_GATE_IO_CONCURRENCY",
                        defaults.categories["io"].concurrency,
                    ),
                ),
            },
        )
