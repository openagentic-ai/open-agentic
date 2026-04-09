"""Chat business logic: conversations and message handling."""

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
    conv = Conversation(user_id=user_id, title=title, model=model, system_prompt=system_prompt)
    db.add(conv)
    await db.flush()
    return conv


async def list_conversations(db: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
    )
    return list(result.scalars().all())


async def get_conversation(db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_conversation(db: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    conv = await get_conversation(db, conv_id, user_id)
    if not conv:
        return False
    await db.delete(conv)
    return True


async def get_messages(db: AsyncSession, conv_id: uuid.UUID) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


def _build_llm_messages(conversation: Conversation, messages: list[Message], user_message: str) -> list[dict]:
    """Build LLM message history from conversation."""
    llm_messages = []
    if conversation.system_prompt:
        llm_messages.append({"role": "system", "content": conversation.system_prompt})
    for msg in messages:
        llm_messages.append({"role": msg.role.value, "content": msg.content})
    llm_messages.append({"role": "user", "content": user_message})
    return llm_messages


async def send_message(
    db: AsyncSession,
    conversation: Conversation,
    user_message: str,
    model: str | None = None,
) -> Message:
    """Send a message and get a non-streaming response."""
    messages = await get_messages(db, conversation.id)
    llm_messages = _build_llm_messages(conversation, messages, user_message)

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_message,
    )
    db.add(user_msg)

    # Call LLM
    result = await chat_completion(llm_messages, model=model or conversation.model)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=result["content"],
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
    """Send a message and stream the response as SSE events."""
    messages = await get_messages(db, conversation.id)
    llm_messages = _build_llm_messages(conversation, messages, user_message)

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_message,
    )
    db.add(user_msg)
    await db.flush()

    # Stream LLM response
    full_content = ""
    async for event in chat_completion_stream(llm_messages, model=model or conversation.model):
        yield event
        # Extract content from event for saving later
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
            pass
