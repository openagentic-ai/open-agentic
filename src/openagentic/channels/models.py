"""模块说明（中文）：`src/openagentic/channels/models.py`。

ChannelConfig DB 模型 —— 持久化用户配置的渠道实例（Telegram/Discord/Slack 等）。
UserChannelBinding —— 把外部渠道账号（飞书 open_id 等）映射到 OpenAgentic User。
"""

import uuid

from sqlalchemy import String, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ChannelConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "channel_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, comment="渠道类型: feishu/wecom/telegram/...")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON 格式的渠道配置（webhook_url, token 等）")


class UserChannelBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """外部渠道账号 → OpenAgentic User 的映射。

    设计要点：
    - (platform, external_id) 全局唯一——同一个飞书 open_id 只会绑到一个 OA User
    - external_id 类型由 platform 隐含决定：feishu=open_id / wecom=user_id / slack=user_id
    - 同一个 User 可在多平台各有一条 binding（一对多）
    """

    __tablename__ = "user_channel_bindings"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_user_channel_bindings_platform_eid"),
        Index("ix_user_channel_bindings_user_id_platform", "user_id", "platform"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, comment="feishu/wecom/slack/...")
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="平台侧账号 ID（飞书=open_id）")
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="发送者显示名（可选，调试用）")
