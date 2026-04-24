"""模块说明（中文）：`src/openagentic/core/chat/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.chat.models import Conversation, Message, MessageRole
from openagentic.core.llm.service import chat_completion, chat_completion_stream


async def create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str = "New Conversation",
    model: str | None = None,
    system_prompt: str | None = None,
) -> Conversation:
    """创建会话记录（仅做持久化，不触发模型调用）。"""
    conv = Conversation(user_id=user_id, title=title, model=model, system_prompt=system_prompt)
    db.add(conv)
    await db.flush()
    return conv


async def list_conversations(db: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    """按更新时间倒序列出用户会话。"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
    )
    return list(result.scalars().all())


async def get_conversation(db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    """按会话 ID + 用户 ID 精确查询，避免越权读取。"""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_conversation(db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """删除会话（若不存在返回 False，调用方决定是否转 404）。"""
    conv = await get_conversation(db, conv_id, user_id)
    if not conv:
        return False
    await db.delete(conv)
    return True


async def get_messages(db: AsyncSession, conv_id: uuid.UUID) -> list[Message]:
    """按时间顺序返回会话消息，供 UI 渲染与 LLM 上下文拼接。"""
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


def _build_llm_messages(conversation: Conversation, messages: list[Message], user_message: str) -> list[dict]:
    """构造 LLM 输入消息列表。

    规则：
    - 若会话有 system_prompt，放在最前；
    - 追加历史消息（按数据库顺序）；
    - 最后追加本轮用户输入。
    """
    llm_messages = []
    if conversation.system_prompt:
        llm_messages.append({"role": "system", "content": conversation.system_prompt})
    for msg in messages:
        entry: dict = {"role": msg.role.value, "content": msg.content}
        if msg.reasoning_content:
            entry["reasoning_content"] = msg.reasoning_content
        llm_messages.append(entry)
    llm_messages.append({"role": "user", "content": user_message})
    return llm_messages


async def send_message(
    db: AsyncSession,
    conversation: Conversation,
    user_message: str,
    model: str | None = None,
) -> Message:
    """非流式发送消息：一次性拿到模型回复并落库。

    写入顺序：
    1) 先写 user 消息；
    2) 调用 LLM；
    3) 再写 assistant 消息；
    这样可保证审计与回放时上下文完整。
    """
    messages = await get_messages(db, conversation.id)
    llm_messages = _build_llm_messages(conversation, messages, user_message)

    # 先保存用户消息，确保即便模型失败，也能保留用户输入轨迹。
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_message,
    )
    db.add(user_msg)

    # 调用模型服务（provider/model 选择由上层参数和会话配置共同决定）。
    result = await chat_completion(llm_messages, model=model or conversation.model)

    # 保存助手回复与 token 统计，后续可用于成本分析。
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=result["content"],
        reasoning_content=result.get("reasoning_content"),
        model=result["model"],
        token_count_input=result["usage"]["prompt_tokens"],
        token_count_output=result["usage"]["completion_tokens"],
    )
    db.add(assistant_msg)
    await db.flush()
    return assistant_msg


async def send_message_stream(
    db: AsyncSession,
    conversation: Conversation,
    user_message: str,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """流式发送消息：边生成边返回 SSE，同时在结束事件后落库完整回复。"""
    messages = await get_messages(db, conversation.id)
    llm_messages = _build_llm_messages(conversation, messages, user_message)

    # 流式场景同样先落 user 消息，保证链路一致性。
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_message,
    )
    db.add(user_msg)
    await db.flush()

    # 把上游模型流直接透传给客户端；遇到 done 事件再写 assistant 最终内容。
    full_content = ""
    async for event in chat_completion_stream(llm_messages, model=model or conversation.model):
        yield event
        # 从 SSE 事件中提取完整回复与 usage，用于最终持久化。
        import json
        try:
            parsed = json.loads(event.replace("data: ", "").strip())
            if parsed.get("event") == "done":
                full_content = parsed.get("data", "")
                usage = parsed.get("usage", {})
                # Save assistant message
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.assistant,
                    content=full_content,
                    model=model or conversation.model,
                    token_count_input=usage.get("prompt_tokens"),
                    token_count_output=usage.get("completion_tokens"),
                )
                db.add(assistant_msg)
                await db.flush()
        except (json.JSONDecodeError, ValueError):
            # 非标准事件直接忽略，避免异常打断流式输出。
            pass
