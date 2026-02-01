"""
ConversationEvent model for storing inbound and outbound chat events.

Immutable events only (insert). Query by channel and external_user_id,
order by created_at to build the full conversation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db import Base
from app.models.mixins import TimestampMixin


class ConversationEvent(Base, TimestampMixin):
    """
    Single event in a conversation (inbound or outbound).

    Stored data is immutable; analysis/enrichment is done by downstream systems.
    """

    __tablename__ = "conversation_events"

    __table_args__ = (
        Index(
            "ix_conversation_events_channel_external_user_created",
            "channel",
            "external_user_id",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction = Column(String(16), nullable=False)  # 'inbound' | 'outbound'
    channel = Column(String(32), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    message_id = Column(String(255), nullable=True)  # platform message id
    text = Column(Text, nullable=True)
    attachments = Column(JSONB, nullable=True, default=list)
    metadata_ = Column("metadata", JSONB, nullable=True, default=dict)
    platform_message_id = Column(String(255), nullable=True)  # for outbound reply id
