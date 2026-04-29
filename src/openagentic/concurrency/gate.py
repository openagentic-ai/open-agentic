"""模块说明（中文）：`src/openagentic/concurrency/gate.py`。

`ConcurrencyGate` —— 并发治理网关主类。

入口契约：

    await gate.submit(
        session_key=...,        # 会话级串行 key（chat_id / user_id / ""）
        coro_factory=...,       # 工厂函数（排队成功后才创建协程，避免悬挂）
        category="llm",         # 走哪一类配额
        timeout=180.0,          # 整体超时（含排队）
    ) -> Any

或细粒度用法（在工具内部局部限流）：

    async with gate.acquire("subprocess"):
        ... # 仅这一段受 subprocess 类别配额限制

执行链路（顺序）：
    1. 排队上限检查（pending >= max_queued → 立即抛 GateBusy）
    2. 全局信号量（global_concurrency 上限）
    3. 类别信号量 + 令牌桶（category 配额）
    4. 会话锁（session_key 内串行）
    5. 实际执行 coro_factory()
    6. 每一层超时由 wait_for 兜底

任何异常向上传播，调用方决定如何处理（飞书层会回 "处理超时" / "处理出错"）。
"""

from __future__ import annotations

import asyncio
import structlog
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, TypeVar

from openagentic.concurrency.config import GateConfig
from openagentic.concurrency.limiter import CategoryLimiter
from openagentic.concurrency.session_lock import SessionLockRegistry

logger = structlog.get_logger("openagentic.concurrency")

T = TypeVar("T")


class GateBusy(Exception):
    """队列已满，请求被拒。调用方应快速失败（飞书层可回退提示用户重试）。"""


class GateTimeout(Exception):
    """整体超时——可能在排队、可能在执行。具体阶段记录在 .stage。"""

    def __init__(self, message: str, stage: str):
        super().__init__(message)
        self.stage = stage


class ConcurrencyGate:
    """并发治理网关。

    单例化使用（get_default_gate）；测试中可独立实例化。
    线程模型：单事件循环、纯 asyncio 原语。多事件循环场景需为每个 loop 创建独立实例。
    """

    def __init__(self, config: GateConfig | None = None):
        self.config = config or GateConfig()
        self._global_sem = asyncio.Semaphore(self.config.global_concurrency)
        self._categories: dict[str, CategoryLimiter] = {
            name: CategoryLimiter(name, cfg)
            for name, cfg in self.config.categories.items()
        }
        self._session_locks = SessionLockRegistry()
        # pending 统计：从 submit 进入到拿到 global_sem 之前的协程数
        self._pending = 0
        # 暴露给 metrics
        self._submitted_total = 0
        self._rejected_total = 0
        self._timeout_total = 0
        self._completed_total = 0

    # -- 主入口 -----------------------------------------------------------

    async def submit(
        self,
        session_key: str,
        coro_factory: Callable[[], Awaitable[T]],
        *,
        category: str = "default",
        timeout: float | None = None,
    ) -> T:
        """提交一个任务到底座，返回执行结果。

        coro_factory 必须是返回 awaitable 的工厂函数（不能直接传 coroutine），
        因为请求可能被拒、可能在排队，提前创建的 coroutine 会泄漏。
        """
        self._submitted_total += 1
        timeout = timeout if timeout is not None else self.config.default_timeout

        # 排队上限——快速失败
        if self._pending >= self.config.max_queued:
            self._rejected_total += 1
            logger.warning(
                "gate.busy",
                pending=self._pending,
                max_queued=self.config.max_queued,
                session_key=session_key,
                category=category,
            )
            raise GateBusy(
                f"queue full ({self._pending}/{self.config.max_queued})"
            )

        limiter = self._get_category(category)
        self._pending += 1
        try:
            return await asyncio.wait_for(
                self._run_inner(session_key, coro_factory, limiter),
                timeout=timeout,
            )
        except asyncio.TimeoutError as e:
            self._timeout_total += 1
            logger.warning(
                "gate.timeout",
                session_key=session_key,
                category=category,
                timeout=timeout,
            )
            raise GateTimeout(
                f"gate timeout after {timeout}s", stage="overall"
            ) from e
        finally:
            self._pending -= 1

    async def _run_inner(
        self,
        session_key: str,
        coro_factory: Callable[[], Awaitable[T]],
        limiter: CategoryLimiter,
    ) -> T:
        """实际执行链：global_sem → category → session_lock → coro_factory()"""
        async with self._global_sem:
            async with limiter.acquire():
                async with self._session_locks.acquire(session_key):
                    self._completed_total += 1
                    return await coro_factory()

    # -- 细粒度入口 --------------------------------------------------------

    @asynccontextmanager
    async def acquire(self, category: str = "default") -> AsyncIterator[None]:
        """直接占用一个类别槽位，用于工具内部的局部限流。

        与 submit 的区别：不走全局信号量、不走会话锁、无超时——
        只把这一段受类别配额保护。适合在 LLM 调用 / 子进程内部叠加。

        典型用法（litellm_chat 内部）：

            async with gate.acquire("llm"):
                response = await litellm.acompletion(...)
        """
        limiter = self._get_category(category)
        async with limiter.acquire():
            yield

    def _get_category(self, name: str) -> CategoryLimiter:
        """取类别 limiter，未配置则回退到 default 并打 warning（仅一次）。"""
        if name in self._categories:
            return self._categories[name]
        logger.warning("gate.unknown_category", category=name, fallback="default")
        return self._categories["default"]

    # -- 可观测性 ---------------------------------------------------------

    def stats(self) -> dict:
        """快照统计——给 /metrics 端点 + 调试用。"""
        return {
            "config": {
                "global_concurrency": self.config.global_concurrency,
                "max_queued": self.config.max_queued,
                "default_timeout": self.config.default_timeout,
            },
            "counters": {
                "submitted": self._submitted_total,
                "completed": self._completed_total,
                "rejected": self._rejected_total,
                "timeout": self._timeout_total,
            },
            "live": {
                "pending": self._pending,
                "global_in_flight": self.config.global_concurrency
                - self._global_sem._value,  # asyncio 内部字段，仅用于观测
            },
            "categories": [c.stats() for c in self._categories.values()],
            "session_locks": self._session_locks.stats(),
        }


# -- 默认实例（单例）----------------------------------------------------

_default_gate: ConcurrencyGate | None = None


def get_default_gate() -> ConcurrencyGate:
    """获取全局默认 gate 实例（懒加载，从 ENV 读配置）。

    所有应用层（飞书/企微/HTTP）都用这一个实例——共享配额、统一排队。
    单测可调 reset_default_gate() 重置。
    """
    global _default_gate
    if _default_gate is None:
        _default_gate = ConcurrencyGate(GateConfig.from_env())
    return _default_gate


def reset_default_gate() -> None:
    """重置默认实例——单测用。生产代码不要调。"""
    global _default_gate
    _default_gate = None
