"""
Normalized message contracts for Conversa.

All inbound messages are converted into these shapes; outbound messages
use the outbound schema. Stable and independent of downstream consumers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Channel(str, Enum):
    """Supported chat channels. WhatsApp, web planned."""

    TELEGRAM = "telegram"
    # WHATSAPP = "whatsapp"
    # WEB = "web"


class MessageMetadata(BaseModel):
    """Metadata for normalized messages (locale, timestamp)."""

    locale: Optional[str] = None
    timestamp: Optional[datetime] = None  # ISO8601


class InboundMessage(BaseModel):
    """Normalized inbound message (adapter → core)."""

    channel: Channel
    external_user_id: str
    message_id: str
    text: str = ""
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)


class OutboundMessage(BaseModel):
    """Normalized outbound message (core → adapter)."""

    channel: Channel
    external_user_id: str  # Telegram: chat_id (e.g. from message.chat.id)
    text: str
    reply_to_message_id: Optional[str] = (
        None  # Optional; omit to send a new message to the chat
    )
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class OutboundSendResult(BaseModel):
    """Result of sending an outbound message (success + optional message_id)."""

    success: bool
    platform_message_id: Optional[str] = None
