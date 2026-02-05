"""
Command to send an outbound message to a chat platform.

Resolves adapter by channel, sends via platform API, persists event on success.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.adapters.base import BasePlatformAdapter
from app.adapters.telegram import TelegramAdapter
from app.config import get_settings
from app.schemas.conversa import Channel, OutboundMessage, OutboundSendResult
from app.services.conversation_event_service import ConversationEventService

logger = logging.getLogger(__name__)


def _adapter_registry() -> dict[Channel, BasePlatformAdapter]:
    """Build adapter registry from config. Only enabled adapters are included."""
    registry: dict[Channel, BasePlatformAdapter] = {}
    settings = get_settings()
    if settings.telegram_enabled and settings.telegram_bot_token:
        registry[Channel.TELEGRAM] = TelegramAdapter(
            bot_token=settings.telegram_bot_token,
            webhook_secret=settings.telegram_webhook_secret,
        )
    return registry


class SendOutboundCommand:
    """
    Command to send an outbound message to the specified channel.
    Resolves adapter by channel, sends, persists on success.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._adapters = _adapter_registry()
        self.conversation_event_service = ConversationEventService(db)

    async def execute(self, body: OutboundMessage) -> dict[str, Any]:
        """
        Send the outbound message via the channel adapter and persist the event.

        Args:
            body: Normalized outbound message (channel, recipient, content, etc.).

        Returns:
            dict: {"data": {"success": True, "platform_message_id": ...}} on success.

        Raises:
            HTTPException: 400 if channel is not enabled or not supported,
                502 if the platform API failed to send.
        """
        adapter = self._adapters.get(body.channel)
        if adapter is None:
            raise HTTPException(
                status_code=400,
                detail=f"Channel {body.channel.value} is not enabled or not supported",
            )
        result: OutboundSendResult = await adapter.send(body)
        if not result.success:
            raise HTTPException(
                status_code=502,
                detail="Platform API failed to send message",
            )
        self.conversation_event_service.create_event_from_outbound(
            body, platform_message_id=result.platform_message_id
        )
        return {
            "data": {
                "success": True,
                "platform_message_id": result.platform_message_id,
            }
        }
