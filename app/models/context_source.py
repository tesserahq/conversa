"""Context source and state models for the Source Registry."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class ContextSource(Base, TimestampMixin, SoftDeleteMixin):
    """Registered context source (e.g. linden-api) for context pack sync."""

    __tablename__ = "context_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    base_url = Column(String(512), nullable=False)
    credential_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    capabilities = Column(JSONB, nullable=True)
    poll_interval_seconds = Column(Integer, nullable=False, default=3600)
    enabled = Column(Boolean, nullable=False, default=True)

    credential = relationship("Credential", backref="context_sources")
    states = relationship(
        "ContextSourceState",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class ContextSourceState(Base):
    """Per-source, per-user sync state (used by the sync worker in Phase 2)."""

    __tablename__ = "context_source_state"

    __table_args__ = (
        UniqueConstraint(
            "source_id", "user_id", name="uq_context_source_state_source_user"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("context_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_success_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    etag = Column(String(256), nullable=True)
    since_cursor = Column(Text, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    source = relationship("ContextSource", back_populates="states")
    user = relationship("User", backref="context_source_states")
