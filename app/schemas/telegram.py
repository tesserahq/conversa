"""
Telegram webhook payload schemas.

Matches the structure Telegram sends to webhook endpoints (message updates).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    """Telegram user (message.from)."""

    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    """Telegram chat (message.chat)."""

    id: int
    type: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessageEntity(BaseModel):
    """Telegram message entity (e.g. bot_command, mention)."""

    offset: int
    length: int
    type: str


class TelegramMessage(BaseModel):
    """Telegram message (update.message)."""

    message_id: int
    from_: TelegramUser = Field(alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    entities: Optional[list[TelegramMessageEntity]] = None

    model_config = {"populate_by_name": True}


class TelegramWebhookUpdate(BaseModel):
    """Telegram webhook update payload (root object)."""

    update_id: int
    message: Optional[TelegramMessage] = None
