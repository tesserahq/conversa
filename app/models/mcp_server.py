"""MCP server registry model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class MCPServer(Base, TimestampMixin, SoftDeleteMixin):
    """Registered external MCP server."""

    __tablename__ = "mcp_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False)
    url = Column(String(512), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    credential_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_prefix = Column(String(64), nullable=True)
    tool_cache_ttl_seconds = Column(Integer, nullable=False, default=300)
    extended_info = Column("metadata", JSONB, nullable=True)

    credential = relationship("Credential", backref="mcp_servers")
