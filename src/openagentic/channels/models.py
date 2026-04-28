"""模块说明（中文）：`src/openagentic/channels/models.py`。

ChannelConfig DB 模型 —— 持久化用户配置的渠道实例（Telegram/Discord/Slack 等）。
"""

import uuid

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ChannelConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "channel_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, comment="渠道类型: feishu/wecom/telegram/...")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON 格式的渠道配置（webhook_url, token 等）")
