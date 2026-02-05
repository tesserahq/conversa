"""
Telegram platform adapter.

Uses python-telegram-bot v13 for parsing webhook payloads and sending messages.
Reference: docs/prompts/bot_example.py for SDK usage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from telegram import Bot, Update

from app.adapters.base import BasePlatformAdapter
from app.schemas.conversa import (
    Channel,
    InboundMessage,
    MessageMetadata,
    OutboundMessage,
    OutboundSendResult,
)


class TelegramAdapter(BasePlatformAdapter):
    """Telegram adapter: parse webhook updates, send messages via Bot API."""

    TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

    def __init__(self, bot_token: str, webhook_secret: Optional[str] = None) -> None:
        self._bot_token = bot_token
        self._webhook_secret = webhook_secret
        self._bot: Optional[Bot] = None

    def _get_bot(self) -> Bot:
        if self._bot is None:
            self._bot = Bot(token=self._bot_token)
        return self._bot

    def verify_webhook(
        self, secret: Optional[str], request_headers: Optional[dict[str, str]] = None
    ) -> bool:
        """Validate X-Telegram-Bot-Api-Secret-Token if webhook secret is configured."""
        expected = secret or self._webhook_secret
        if not expected:
            return True
        request_headers = request_headers or {}
        header_lower = self.TELEGRAM_SECRET_HEADER.lower()
        actual = None
        for key, value in request_headers.items():
            if key.lower() == header_lower:
                actual = value
                break
        return actual == expected

    def parse_webhook(self, raw_payload: dict[str, Any]) -> InboundMessage:
        """Parse Telegram webhook payload into normalized inbound message."""
        update = Update.de_json(raw_payload, self._get_bot())
        if update is None:
            raise ValueError("Invalid Telegram update: de_json returned None")
        if not update.message:
            raise ValueError("Telegram update has no message")
        msg = update.message
        from_user = msg.from_user
        chat_id = (
            str(msg.chat_id)
            if msg.chat_id
            else (str(from_user.id) if from_user else "")
        )
        user_id = str(from_user.id) if from_user else chat_id
        text = msg.text or ""
        message_id = str(msg.message_id) if msg.message_id else ""
        attachments: list[dict[str, Any]] = []
        if msg.photo:
            attachments.append(
                {"type": "photo", "file_ids": [p.file_id for p in msg.photo]}
            )
        if msg.document:
            attachments.append({"type": "document", "file_id": msg.document.file_id})
        if msg.voice:
            attachments.append({"type": "voice", "file_id": msg.voice.file_id})
        locale = (
            from_user.language_code if from_user and from_user.language_code else None
        )
        ts = msg.date
        if ts:
            ts_utc = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        else:
            ts_utc = datetime.now(timezone.utc)
        metadata = MessageMetadata(locale=locale, timestamp=ts_utc)
        return InboundMessage(
            channel=Channel.TELEGRAM,
            external_user_id=chat_id,
            message_id=message_id,
            text=text,
            attachments=attachments,
            metadata=metadata,
        )

    async def send(self, outbound: OutboundMessage) -> OutboundSendResult:
        """Send message via Telegram Bot API. chat_id = external_user_id."""
        if outbound.channel != Channel.TELEGRAM:
            return OutboundSendResult(success=False, platform_message_id=None)

        send_kw: dict[str, Any] = {
            "chat_id": outbound.external_user_id,
            "text": outbound.text,
            "reply_to_message_id": (
                int(outbound.reply_to_message_id)
                if outbound.reply_to_message_id
                else None
            ),
        }
        if outbound.parse_mode:
            send_kw["parse_mode"] = outbound.parse_mode
        sent = await self._get_bot().send_message(**send_kw)
        return OutboundSendResult(
            success=True,
            platform_message_id=(
                str(sent.message_id) if sent and sent.message_id else None
            ),
        )
