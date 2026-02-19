"""Pydantic schemas for Session and SessionMessage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Session origin (optional nested model for Session.origin JSONB)
# -----------------------------------------------------------------------------


class SessionOrigin(BaseModel):
    """Optional metadata for where a session came from (label, from, to, etc.)."""

    label: Optional[str] = None
    from_id: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    account_id: Optional[str] = None
    thread_id: Optional[str] = None

    model_config = {"populate_by_name": True}


# -----------------------------------------------------------------------------
# Session schemas
# -----------------------------------------------------------------------------


class SessionBase(BaseModel):
    """Base session fields."""

    session_key: str
    user_id: Optional[UUID] = None
    channel: str
    account_id: Optional[str] = None
    chat_id: str
    thread_id: Optional[str] = None
    display_name: Optional[str] = None
    origin: Optional[dict[str, Any] | SessionOrigin] = None
    last_message_at: datetime


class SessionCreate(BaseModel):
    """Schema for creating a session."""

    session_key: str
    user_id: Optional[UUID] = None
    channel: str
    account_id: Optional[str] = None
    chat_id: str
    thread_id: Optional[str] = None
    display_name: Optional[str] = None
    origin: Optional[dict[str, Any] | SessionOrigin] = None
    last_message_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class SessionUpdate(BaseModel):
    """Schema for updating a session. All fields optional."""

    user_id: Optional[UUID] = None
    channel: Optional[str] = None
    account_id: Optional[str] = None
    chat_id: Optional[str] = None
    thread_id: Optional[str] = None
    display_name: Optional[str] = None
    origin: Optional[dict[str, Any]] = None
    last_message_at: Optional[datetime] = None


class SessionInDB(SessionBase):
    """Session as stored in DB (includes id and timestamps)."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SessionRead(SessionInDB):
    """Session for API responses."""

    pass


# -----------------------------------------------------------------------------
# SessionMessage schemas
# -----------------------------------------------------------------------------

MessageDirection = Literal["inbound", "outbound"]


class MessageBase(BaseModel):
    """Base message fields."""

    direction: MessageDirection
    content: Optional[str] = None
    provider_message_id: Optional[str] = None
    reply_to: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class MessageCreate(MessageBase):
    """Schema for creating a session message."""

    pass


class MessageInDB(MessageBase):
    """Session message as stored in DB."""

    id: UUID
    session_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if hasattr(obj, "message_metadata"):
            # ORM has .extra as DB column; expose as .metadata for schema
            if isinstance(obj, dict):
                return super().model_validate(obj, **kwargs)
            data = {
                "id": getattr(obj, "id", None),
                "session_id": getattr(obj, "session_id", None),
                "direction": getattr(obj, "direction", None),
                "content": getattr(obj, "content", None),
                "provider_message_id": getattr(obj, "provider_message_id", None),
                "reply_to": getattr(obj, "reply_to", None),
                "metadata": getattr(obj, "message_metadata", None)
                or getattr(obj, "extra", None),
                "created_at": getattr(obj, "created_at", None),
            }
            return cls.model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


class MessageRead(MessageInDB):
    """Session message for API responses."""

    pass


class SessionListRow(SessionRead):
    """Session row for list endpoints; optional messages and message_count."""

    messages: Optional[list[MessageRead]] = None
    message_count: Optional[int] = None


# -----------------------------------------------------------------------------
# Session expiry config (optional; loaded from app config/settings)
# -----------------------------------------------------------------------------


class SessionExpiryConfig(BaseModel):
    """Config for daily/idle session expiry."""

    mode: Literal["off", "daily", "idle"] = "off"
    at_hour: int = Field(default=4, ge=0, le=23)
    idle_minutes: Optional[int] = Field(default=None, ge=1)


# -----------------------------------------------------------------------------
# Reset options (optional)
# -----------------------------------------------------------------------------


class SessionResetOptions(BaseModel):
    """Options when resetting a session (e.g. archive old messages)."""

    archive_old_messages: bool = False
