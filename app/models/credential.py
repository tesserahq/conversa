"""Credential model for storing encrypted credentials (context source auth)."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Credential(Base, TimestampMixin, SoftDeleteMixin):
    """Credential model for storing encrypted credentials.

    Used by context sources for auth when fetching context packs.
    Secrets are encrypted using Fernet before storage.
    """

    __tablename__ = "credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False, index=True)
    encrypted_data = Column(LargeBinary, nullable=False)
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by = relationship("User", backref="credentials")
