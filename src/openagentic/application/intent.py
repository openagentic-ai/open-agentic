"""Intent 抽象——中性语义命令。

替代 channel_runner.py 中 _fast_path_reply() 文本硬匹配。同一 Intent 在不同端的触发方式不同:

- IM: 文本匹配("/run x" / "启动 x")
- Web/Android: 按钮点击 / 列表选择
- 触发器(Android): 位置进入地理围栏 / 特定时间 / 特定通知

但**执行链路相同**——都走 IntentRouter.dispatch(),共享业务逻辑。

参考: docs/ADR-001-multi-adapter-foundation.md §6
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Intent:
    """中性 intent。"""
    name: str                                # "list_workflows" | "run_workflow" | "query_run" | "session_status"
    params: dict[str, Any] = field(default_factory=dict)
    source: str = ""                         # "im_text" | "client_button" | "trigger_geo" | "trigger_schedule" | ...


class IntentRouter(Protocol):
    """Intent 路由分发。"""

    async def dispatch(self, intent: Intent, *, user_id: str, session_id: str) -> Any:
        """执行 intent,返回结构化结果(各端自行渲染)。"""
        ...

    def register(self, name: str, handler) -> None:
        """注册 intent 处理函数。Phase 1 把 _fast_*  方法迁过来。"""
        ...
