"""DefaultOrchestrator——ConversationOrchestrator 默认实现。

核心难点: ConversationEngine.chat() 同步返回 str,这里要包成
AsyncIterator[ReplyEvent] 流。方案:

1. 创建 asyncio.Queue[ReplyEvent | None](None=终止哨兵)
2. 起 background task 跑 engine.chat(messages):
   - engine 的 on_thinking / on_tool_call / on_tool_result hooks → put 到 queue
   - chat 返回 → put FinalEvent → put None
   - chat 抛异常 → put ErrorEvent → put None
3. 主协程 yield from queue 直到拿到 None

不知道 webhook / WebSocket / SDK / 卡片——任何 L4 渲染都在 adapter 层做。

参考: docs/ADR-001-multi-adapter-foundation.md §1, §2
"""
from __future__ import annotations

import asyncio
import structlog
from typing import AsyncIterator

from openagentic.agent.engine import ConversationEngine
from openagentic.application.events import (
    ReplyEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    FinalEvent,
    ErrorEvent,
)
from openagentic.application.session import Session
from openagentic.application.tool_registry import ToolSpec
from openagentic.application.tool_registry_default import DefaultToolRegistry

logger = structlog.get_logger("openagentic.application.orchestrator")

MAX_HISTORY = 20  # 与 channel_runner 对齐
DEFAULT_MAX_ITERATIONS = 30  # 与 channel_runner.MAX_TOOL_ITERATIONS 对齐


class DefaultOrchestrator:
    """共同底座对话编排默认实现。

    - history: 内置 dict[session_id, list[dict]],进程内存(Phase 1 够用)
    - tools: 由 DefaultToolRegistry 按 session.adapter_id 提供
    - memory: episodic/procedural 注入复用 MemoryManager(可选,失败仅 warning)
    - executor: 由调用方注入(adapter 层负责把 tool 名 → 真实 handler 派发)
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        api_base: str | None,
        system_prompt: str,
        tool_registry: DefaultToolRegistry,
        executor=None,
        guard=None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        enable_memory: bool = True,
    ):
        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._system_prompt = system_prompt
        self._tool_registry = tool_registry
        self._executor = executor
        self._guard = guard
        self._max_iterations = max_iterations
        self._enable_memory = enable_memory
        self._histories: dict[str, list[dict]] = {}
        self._history_locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        lock = self._history_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._history_locks[session_id] = lock
        return lock

    async def _build_executor(self, session: Session):
        """如未注入全局 executor,则构造按 ToolRegistry 派发的默认 executor。"""
        if self._executor is not None:
            return self._executor

        registry = self._tool_registry

        async def _dispatch(name: str, args: dict) -> str:
            spec: ToolSpec | None = registry.get(name)
            if spec is None:
                return f"工具 {name} 未注册"
            try:
                result = await spec.handler(**args)
            except TypeError:
                # handler 可能签名为 (args: dict) 而非 **args
                result = await spec.handler(args)
            return result if isinstance(result, str) else str(result)

        return _dispatch

    async def _inject_memory(self, messages: list[dict], user_text: str) -> None:
        """复用 MemoryManager 注入 episodic/procedural 上下文。失败仅 warning。"""
        if not self._enable_memory:
            return
        try:
            from openagentic.memory.manager import MemoryManager
        except Exception as exc:
            logger.debug("memory module unavailable", error=str(exc))
            return

        try:
            eps = await asyncio.to_thread(MemoryManager().search_episodes, user_text, 3)
            if eps:
                ctx = "## Relevant Past Experiences\n\n"
                for i, ep in enumerate(eps, 1):
                    ctx += f"{i}. {ep['title']}\n   {ep['summary'][:300]}\n\n"
                messages.insert(1, {"role": "system", "content": ctx})
        except Exception as exc:
            logger.warning("episodic memory injection failed", error=str(exc))

        try:
            procs = await asyncio.to_thread(MemoryManager().search_procedures, user_text, 3)
            if procs:
                ctx = "## Relevant Procedures\n\n"
                for i, p in enumerate(procs, 1):
                    ctx += f"{i}. {p['name']}\n   {p['content'][:300]}\n\n"
                messages.insert(1, {"role": "system", "content": ctx})
        except Exception as exc:
            logger.warning("procedural memory injection failed", error=str(exc))

    async def reply(self, session: Session, user_text: str) -> AsyncIterator[ReplyEvent]:
        """流式回复,事件序列: thinking* (tool_call tool_result)* final|error。"""
        sid = session.session_id
        seq = 0

        def _next_seq() -> int:
            nonlocal seq
            seq += 1
            return seq

        # ── 准备 messages ────────────────────────────────────────────────
        async with self._lock_for(sid):
            history = self._histories.setdefault(sid, [])
            messages: list[dict] = [
                {"role": "system", "content": self._system_prompt},
                *history[-MAX_HISTORY:],
            ]
            await self._inject_memory(messages, user_text)
            messages.append({"role": "user", "content": user_text})

            # ── 构造 engine + queue + hooks ─────────────────────────────
            queue: asyncio.Queue[ReplyEvent | None] = asyncio.Queue()
            sentinel: object = object()

            async def _emit(ev: ReplyEvent) -> None:
                await queue.put(ev)

            async def on_thinking(text: str) -> None:
                await _emit(ThinkingEvent(session_id=sid, seq=_next_seq(), text=text))

            async def on_tool_call(call_id: str, tool_name: str, tool_args: dict) -> None:
                await _emit(ToolCallEvent(
                    session_id=sid, seq=_next_seq(),
                    tool_name=tool_name, tool_args=tool_args, call_id=call_id,
                ))

            async def on_tool_result(call_id: str, result: str, error: str | None) -> None:
                await _emit(ToolResultEvent(
                    session_id=sid, seq=_next_seq(),
                    call_id=call_id, result=result, error=error,
                ))

            executor = await self._build_executor(session)
            tools_schema = self._tool_registry.litellm_schema_for(session.adapter_id)

            engine = ConversationEngine(
                model=self._model,
                api_key=self._api_key,
                api_base=self._api_base,
                tools=tools_schema,
                system_prompt=self._system_prompt,
                max_iterations=self._max_iterations,
                executor=executor,
                guard=self._guard,
                on_thinking=on_thinking,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )

            # ── background task 跑 chat,完成后投终态 ─────────────────────
            async def _run() -> None:
                try:
                    reply_text = await engine.chat(messages)
                    await _emit(FinalEvent(session_id=sid, seq=_next_seq(), text=reply_text))
                except Exception as exc:
                    logger.exception("orchestrator chat failed", session_id=sid)
                    await _emit(ErrorEvent(
                        session_id=sid, seq=_next_seq(),
                        code="chat_failed", message=str(exc),
                    ))
                finally:
                    await queue.put(None)  # 终止哨兵

            task = asyncio.create_task(_run())

            # 启动事件——总在 LLM 第一次 thinking 之前给 L4 一个反馈
            yield ThinkingEvent(session_id=sid, seq=_next_seq(), text="收到,开始处理")

            final_text: str | None = None
            try:
                while True:
                    ev = await queue.get()
                    if ev is None:
                        break
                    if isinstance(ev, FinalEvent):
                        final_text = ev.text
                    yield ev
            finally:
                # 确保 background task 不泄漏
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass

            # 持久化到 history(只在 final 成功时写)
            if final_text is not None:
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": final_text})


__all__ = ["DefaultOrchestrator"]
