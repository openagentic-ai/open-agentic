"""模块说明（中文）：`src/openagentic/concurrency/session_lock.py`。

按 key 的会话锁注册表——同 key 严格串行，防止同会话两条消息并发改写历史。

为什么需要：
飞书同一群里（chat_id 相同）两条紧挨消息会并发派发到 ai.reply()，
ChannelAIService._histories[chat_id] 是无锁的 dict.list，会出现：
- 两个协程同时读到旧 history，两份独立修改，后写覆盖先写 → 中间消息丢失
- 工具调用与历史追加交错 → 后续 LLM 看到错乱的 messages

解决：同 chat_id 走同一把 asyncio.Lock，串行 reply。

设计要点：
- 弱引用？asyncio.Lock 不可弱引用，改用引用计数 + 显式回收
- 锁池太大也是泄漏，按 LRU 上限 + idle 回收
- session_key 为空时不加锁（兼容无会话语义的请求，如 HTTP 单次调用）
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import AsyncIterator


class SessionLockRegistry:
    """按 key 复用 asyncio.Lock，引用计数防内存泄漏。

    每次 acquire(key) 会创建/复用一把锁、ref_count+1；
    退出 with 块时 ref_count-1，归零时从注册表移除。

    LRU 上限 max_keys：超过时把最旧的、ref_count==0 的项淘汰。
    """

    def __init__(self, max_keys: int = 10000):
        self._max_keys = max_keys
        self._locks: OrderedDict[str, tuple[asyncio.Lock, int]] = OrderedDict()
        # _meta_lock 保护 _locks 字典本身的并发修改；
        # 业务锁（asyncio.Lock）拿到后直接 await，不在 _meta_lock 内部 await。
        self._meta_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncIterator[None]:
        """获取 key 对应的会话锁，with 块内独占执行。

        key 为空 → no-op，直接 yield，不加锁（无会话语义）。
        """
        if not key:
            yield
            return

        lock = await self._checkout(key)
        try:
            async with lock:
                yield
        finally:
            await self._checkin(key)

    async def _checkout(self, key: str) -> asyncio.Lock:
        async with self._meta_lock:
            entry = self._locks.get(key)
            if entry is None:
                lock = asyncio.Lock()
                self._locks[key] = (lock, 1)
            else:
                lock, ref = entry
                self._locks[key] = (lock, ref + 1)
            self._locks.move_to_end(key)
            self._evict_if_needed()
            return lock

    async def _checkin(self, key: str) -> None:
        async with self._meta_lock:
            entry = self._locks.get(key)
            if entry is None:
                return
            lock, ref = entry
            ref -= 1
            if ref <= 0:
                self._locks.pop(key, None)
            else:
                self._locks[key] = (lock, ref)

    def _evict_if_needed(self) -> None:
        """LRU 淘汰：仅淘汰 ref_count==0 的项，避免抢走在用的锁。

        这是保险机制——正常路径 _checkin 已经清理；
        长尾极端场景（注册多但都还在用）可能淘汰不掉，依赖 max_keys 设大一点。
        """
        if len(self._locks) <= self._max_keys:
            return
        # 从最旧开始扫，删掉第一个 ref_count==0 的
        for k in list(self._locks.keys()):
            if self._locks[k][1] == 0:
                self._locks.pop(k, None)
                if len(self._locks) <= self._max_keys:
                    return

    def stats(self) -> dict:
        """暴露给 metrics/调试用——锁数量与最大引用数。"""
        if not self._locks:
            return {"active_keys": 0, "max_ref": 0}
        return {
            "active_keys": len(self._locks),
            "max_ref": max(ref for _, ref in self._locks.values()),
        }
