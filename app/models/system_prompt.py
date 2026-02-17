"""System prompt and version models for configurable LLM system prompts (markdown)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class SystemPrompt(Base, TimestampMixin):
    """One row per logical prompt (e.g. 'default'). Points to current version."""

    __tablename__ = "system_prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), unique=True, nullable=False, index=True)
    current_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    current_version = relationship(
        "SystemPromptVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions = relationship(
        "SystemPromptVersion",
        back_populates="system_prompt",
        foreign_keys="SystemPromptVersion.system_prompt_id",
        cascade="all, delete-orphan",
        order_by="SystemPromptVersion.version_number.desc()",
    )


class SystemPromptVersion(Base):
    """One row per change; content is markdown. History is append-only."""

    __tablename__ = "system_prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_prompt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    version_number = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    note = Column(String(512), nullable=True)

    system_prompt = relationship(
        "SystemPrompt",
        back_populates="versions",
        foreign_keys=[system_prompt_id],
    )
