"""Context snapshot model: merged context pack stored per user."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db import Base


class ContextSnapshot(Base):
    """Stored merged context pack for a user (chat-time read)."""

    __tablename__ = "context_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_version = Column(String(32), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSONB, nullable=False)
    payload_hash = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
