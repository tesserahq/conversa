"""ChannelInstallation model — stores per-workspace OAuth bot tokens for channel integrations."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class ChannelInstallation(Base, TimestampMixin, SoftDeleteMixin):
    """One row per installed workspace/account for a channel (Slack, WhatsApp, Teams, etc.).

    Plaintext columns are safe to query on. Sensitive fields (e.g. bot_token) are
    stored Fernet-encrypted in encrypted_data as a JSON blob.
    """

    __tablename__ = "channel_installations"
    __table_args__ = (
        UniqueConstraint(
            "channel", "account_id", name="uq_channel_installation_account"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(64), nullable=False, index=True)
    account_id = Column(String(256), nullable=False, index=True)
    account_name = Column(String(256), nullable=True)
    bot_user_id = Column(String(256), nullable=True)
    installer_user_id = Column(String(256), nullable=True)
    scopes = Column(String(1024), nullable=True)
    encrypted_data = Column(LargeBinary, nullable=False)
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by = relationship("User", backref="channel_installations")
