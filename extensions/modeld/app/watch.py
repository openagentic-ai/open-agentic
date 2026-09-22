"""模块说明（中文）：`app/watch.py`。

守护循环——定期确保模型可用。

为什么必须在线程里跑 ensure：拉起模型含最长 900 秒的阻塞调用，
直接 await 会把事件循环卡死（守卫自身的 HTTP 接口也一起失去响应）。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("modeld.watch")


async def run_watch_loop(ensure_fn, interval_sec: float, stop: asyncio.Event) -> None:
    """周期性执行一次 ensure，直到 stop 被置位。

    单次失败只记日志不退出——否则一次网络抖动就会永久失去守护。
    """
    while not stop.is_set():
        try:
            result = await asyncio.to_thread(ensure_fn)
            payload = getattr(result, "payload", None) or result
            action = payload.get("action") if isinstance(payload, dict) else None
            if action and action not in ("none",):
                logger.info("watch ensure: action=%s detail=%s", action, payload.get("reason") or payload.get("state"))
        except Exception:
            logger.warning("watch cycle failed", exc_info=True)

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_sec)
        except asyncio.TimeoutError:
            pass
