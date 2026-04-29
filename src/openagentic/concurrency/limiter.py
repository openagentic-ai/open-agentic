"""模块说明（中文）：`src/openagentic/concurrency/limiter.py`。

类别信号量 + 令牌桶限流。

类别信号量：每个 category（llm / subprocess / io）独立配额，互不干扰。
令牌桶：可选叠加在信号量之上——信号量管"同时进行多少"，令牌桶管"每秒放多少"。

为什么两层叠加：
- 单纯信号量：若 LLM 调用平均 100ms 完成，30 并发 × 10 次/秒 = 300 QPS，撞 provider 限流
- 单纯令牌桶：若 50/s 但每次调用 10s，会堆积 500 个 in-flight 协程
- 叠加：30 并发 上限 + 50/s 速率 上限，双闸门，平稳

数学：100 量级飞书并发 → LLM 30 并发已是上限，令牌桶 50/s 是软保护。
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from openagentic.concurrency.config import CategoryConfig


class TokenBucket:
    """简单异步令牌桶。

    rate_per_sec 速率补充，capacity 上限。
    take(n=1) 如果不足会 await 到补满。
    """

    def __init__(self, rate_per_sec: float, capacity: int):
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be > 0")
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._rate = rate_per_sec
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def take(self, n: int = 1) -> None:
        """取 n 个令牌；不够则 sleep 到够。"""
        if n > self._capacity:
            raise ValueError(f"requested {n} > capacity {self._capacity}")
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return
                # 计算还差多少令牌、需要 sleep 多久
                need = n - self._tokens
                wait = need / self._rate
            # 释放锁后再 sleep——别的协程可能在此期间归还令牌
            await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now


class CategoryLimiter:
    """单个类别的并发控制：信号量（必有）+ 令牌桶（可选）。"""

    def __init__(self, name: str, cfg: CategoryConfig):
        if cfg.concurrency <= 0:
            raise ValueError(f"category {name}: concurrency must be > 0")
        self.name = name
        self._sem = asyncio.Semaphore(cfg.concurrency)
        self._max = cfg.concurrency
        self._bucket: TokenBucket | None = None
        if cfg.rate_per_sec and cfg.rate_per_sec > 0:
            burst = cfg.burst or cfg.concurrency
            self._bucket = TokenBucket(cfg.rate_per_sec, burst)
        # 暴露给 metrics 用
        self._in_flight = 0

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """获取本类别配额 + 令牌（如有），with 块内占用一个槽位。"""
        if self._bucket is not None:
            await self._bucket.take(1)
        await self._sem.acquire()
        self._in_flight += 1
        try:
            yield
        finally:
            self._in_flight -= 1
            self._sem.release()

    def stats(self) -> dict:
        return {
            "name": self.name,
            "max": self._max,
            "in_flight": self._in_flight,
            "available": self._max - self._in_flight,
        }
