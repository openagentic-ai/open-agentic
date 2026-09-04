"""模块说明（中文）：`src/openagentic/context/manager.py`。

上下文工程管线（ContextManager）——对标 Anthropic 的上下文焦虑防御 + OpenAI 的快照/恢复。

三层策略：
  1. compress_tool_outputs：LLM 调用前压缩超长工具输出，用摘要替代原文
  2. compact_history：接近窗口极限时压缩旧消息为摘要
  3. snapshot / restore：持久化会话状态，crash 后可恢复

设计：
  - 复用 memory/manager.py 的 estimate_tokens 和 compress_working_memory
  - 环境变量 OPENAGENTIC_CONTEXT_MANAGER=1 激活
  - 通过 ConversationEngine 的 on_before_chat callback 注入
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("openagentic.context")

# ── 环境变量 ──────────────────────────────────────────────
ENABLED = os.environ.get("OPENAGENTIC_CONTEXT_MANAGER", "0") == "1"
CONTEXT_MAX_TOKENS = int(os.environ.get("OPENAGENTIC_CONTEXT_MAX_TOKENS", "80000"))
TOOL_OUTPUT_MAX_CHARS = int(os.environ.get("OPENAGENTIC_CONTEXT_TOOL_OUTPUT_MAX", "4000"))
KEEP_RECENT = int(os.environ.get("OPENAGENTIC_CONTEXT_KEEP_RECENT", "10"))
SNAPSHOT_DIR = Path(os.environ.get(
    "OPENAGENTIC_CONTEXT_SNAPSHOT_DIR",
    str(Path.home() / ".openagentic" / "snapshots"),
))


class ContextManager:
    """上下文工程管线。

    用法::

        cm = ContextManager()

        # 作为 engine callback 注入
        engine = ConversationEngine(
            ...,
            on_before_chat=cm.as_before_chat_hook(),
        )

        # 或手动调用
        messages = cm.maybe_compact(messages)
        cm.snapshot(messages, "run-123")
    """

    def __init__(
        self,
        max_tokens: int = CONTEXT_MAX_TOKENS,
        tool_output_max_chars: int = TOOL_OUTPUT_MAX_CHARS,
        keep_recent: int = KEEP_RECENT,
        snapshot_dir: Path | None = None,
        model: str = "",
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        self.max_tokens = max_tokens
        self.tool_output_max_chars = tool_output_max_chars
        self.keep_recent = keep_recent
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else SNAPSHOT_DIR
        self.model = model
        self.api_base = api_base
        self.api_key = api_key

    # ── Layer 1: 工具输出压缩 ─────────────────────────────

    def compress_tool_outputs(self, messages: list[dict]) -> list[dict]:
        """压缩超长工具输出。

        对每个 tool role 的消息，如果 content 超过 tool_output_max_chars，
        保留前 200 字符 + 摘要标记 + 后 200 字符。
        保持原始 messages 列表不变，返回新列表。
        """
        if not messages:
            return messages

        result: list[dict] = []
        changed = False
        for msg in messages:
            if msg.get("role") != "tool":
                result.append(msg)
                continue

            content = msg.get("content", "") or ""
            if len(content) <= self.tool_output_max_chars:
                result.append(msg)
                continue

            # 压缩：头 + 尾 + 中间摘要
            head = content[:200]
            tail = content[-200:] if len(content) > 400 else ""
            truncated = (
                f"{head}\n"
                f"... [中间 {len(content) - 400} 字符已省略] ...\n"
                f"{tail}"
            )
            result.append({**msg, "content": truncated})
            changed = True

        if changed:
            logger.debug(
                "compress_tool_outputs: truncated long tool results",
            )
        return result

    # ── Layer 2: 历史压缩 ─────────────────────────────────

    def needs_compaction(self, messages: list[dict]) -> bool:
        """检查消息列表是否需要压缩。"""
        from openagentic.memory.manager import estimate_tokens
        return estimate_tokens(messages) > self.max_tokens

    async def compact_history(self, messages: list[dict]) -> list[dict]:
        """压缩旧消息为摘要，保留最近 N 条。

        复用 memory/manager.py 的 compress_working_memory，传入
        当前 ContextManager 的配置参数。
        """
        from openagentic.memory.manager import (
            compress_working_memory,
            estimate_tokens,
            working_memory_compressible,
        )

        if not working_memory_compressible(messages, self.max_tokens):
            return messages

        logger.info(
            "compacting history",
            current_tokens=estimate_tokens(messages),
            max_tokens=self.max_tokens,
            message_count=len(messages),
        )

        try:
            compressed = await compress_working_memory(
                messages,
                keep_recent=self.keep_recent,
                model=self.model,
                api_base=self.api_base,
                api_key=self.api_key,
            )
            new_tokens = estimate_tokens(compressed)
            logger.info(
                "history compacted",
                before_tokens=estimate_tokens(messages),
                after_tokens=new_tokens,
                before_count=len(messages),
                after_count=len(compressed),
            )
            return compressed
        except Exception:
            logger.exception("compact_history failed, returning original messages")
            return messages

    def maybe_compact(self, messages: list[dict]) -> list[dict]:
        """同步检查 + 压缩（不调用 LLM，仅截断工具输出）。

        用于不想阻塞的快速路径。LLM 压缩走 compact_history()。
        """
        return self.compress_tool_outputs(messages)

    # ── Layer 3: 快照与恢复 ───────────────────────────────

    def snapshot(self, messages: list[dict], run_id: str) -> Path:
        """持久化当前会话消息到磁盘。

        Returns:
            快照文件路径。
        """
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.snapshot_dir / f"{run_id}.json"

        payload = {
            "run_id": run_id,
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(messages),
            "estimated_tokens": self._estimate(messages),
            "messages": messages,
        }
        snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("snapshot saved", path=str(snapshot_path), run_id=run_id)
        return snapshot_path

    @staticmethod
    def restore(run_id: str, snapshot_dir: Path | None = None) -> list[dict] | None:
        """从磁盘恢复会话消息。

        Returns:
            消息列表；文件不存在或损坏则返回 None。
        """
        sd = Path(snapshot_dir) if snapshot_dir else SNAPSHOT_DIR
        snapshot_path = sd / f"{run_id}.json"
        if not snapshot_path.is_file():
            return None

        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            messages = payload.get("messages", [])
            logger.info(
                "snapshot restored",
                path=str(snapshot_path),
                run_id=run_id,
                message_count=len(messages),
            )
            return messages
        except (json.JSONDecodeError, KeyError):
            logger.exception("snapshot restore failed", path=str(snapshot_path))
            return None

    # ── Engine hook ────────────────────────────────────────

    def as_before_chat_hook(self):
        """返回可直接注入 ConversationEngine(on_before_chat=...) 的 callback。"""
        return self.before_chat_hook

    async def before_chat_hook(self, messages: list[dict]) -> str | None:
        """ConversationEngine 的 on_before_chat callback。

        在每次 LLM 调用前执行：
          1. 压缩超长工具输出
          2. 检查 token 预算，必要时压缩历史
          3. 不返回注入文本（压缩直接修改 messages 列表）

        Returns:
            None——此 hook 通过副作用修改 messages，不注入 system prompt。
        """
        # Layer 1: 压缩工具输出（同步，零延迟）
        for i, msg in enumerate(messages):
            if msg.get("role") == "tool":
                content = msg.get("content", "") or ""
                if len(content) > self.tool_output_max_chars:
                    head = content[:200]
                    tail = content[-200:] if len(content) > 400 else ""
                    messages[i] = {
                        **msg,
                        "content": (
                            f"{head}\n"
                            f"... [中间 {len(content) - 400} 字符已省略] ...\n"
                            f"{tail}"
                        ),
                    }

        # Layer 2: 检查是否需要 LLM 压缩
        from openagentic.memory.manager import working_memory_compressible
        if working_memory_compressible(messages, self.max_tokens):
            logger.warning(
                "context approaching limit, compaction recommended",
                estimated_tokens=self._estimate(messages),
                max_tokens=self.max_tokens,
            )
            # 注意：这里不自动触发 LLM 压缩，避免阻塞用户消息。
            # 调用方应在外层处理（如 channel_runner 的压缩逻辑）。
            # 只做同步截断。

        return None  # 不注入 system prompt 文本

    # ── helpers ────────────────────────────────────────────

    @staticmethod
    def _estimate(messages: list[dict]) -> int:
        """估算 token 数。"""
        from openagentic.memory.manager import estimate_tokens
        return estimate_tokens(messages)
