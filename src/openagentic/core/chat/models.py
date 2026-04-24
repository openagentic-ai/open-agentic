"""模块说明（中文）：`src/openagentic/core/chat/models.py`。\n\n该文件定义数据库模型与持久化结构。\n"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MessageRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), default="New Conversation")
    model: Mapped[str] = mapped_column(String(100), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", lazy="selectin", order_by="Message.created_at")


class Message(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_count_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default="now()"
    )

    conversation = relationship("Conversation", back_populates="messages")
