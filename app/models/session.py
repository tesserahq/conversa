"""Session model: one row per conversation bucket (channel + chat + optional thread)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Session(Base, TimestampMixin, SoftDeleteMixin):
    """One row per conversation bucket. Identified by session_key (e.g. channel:chat_id or channel:chat_id:thread:id)."""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_key = Column(String(512), unique=True, nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channel = Column(String(64), nullable=False)
    account_id = Column(String(256), nullable=True)
    chat_id = Column(String(256), nullable=False)
    thread_id = Column(String(256), nullable=True)
    display_name = Column(String(256), nullable=True)
    origin = Column(JSONB, nullable=True)
    last_message_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    messages = relationship(
        "SessionMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionMessage.created_at",
    )
