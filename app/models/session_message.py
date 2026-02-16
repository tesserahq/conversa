"""SessionMessage model: one row per inbound or outbound message in a session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base


class SessionMessage(Base):
    """One row per message; direction is 'inbound' (from user/channel) or 'outbound' (gateway reply)."""

    __tablename__ = "session_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction = Column(String(16), nullable=False)  # 'inbound' | 'outbound'
    content = Column(Text, nullable=True)
    provider_message_id = Column(String(256), nullable=True)
    reply_to = Column(String(256), nullable=True)
    extra = Column(
        "metadata", JSONB, nullable=True
    )  # DB column "metadata"; avoid shadowing Base.metadata
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    session = relationship("Session", back_populates="messages")

    @property
    def message_metadata(self) -> dict | None:
        """Expose DB column 'metadata' for Pydantic/serialization (avoid shadowing Base.metadata)."""
        return self.extra
