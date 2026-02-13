from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class Media(BaseModel):
    kind: str
    url: Optional[str] = None
    mime_type: Optional[str] = None
    bytes_b64: Optional[str] = None


class InboundMessage(BaseModel):
    channel: str
    account_id: Optional[str]
    sender_id: str
    chat_id: str
    thread_id: Optional[str]
    message_id: str
    text: Optional[str]
    media: list[Media] = []
    timestamp: datetime
    raw: dict[str, Any]


class OutboundMessage(BaseModel):
    channel: str
    account_id: Optional[str]
    chat_id: str
    thread_id: Optional[str]
    text: Optional[str]
    media: list[Media] = []
    reply_to: Optional[str]
