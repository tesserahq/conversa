"""
Outbound API: send messages via Conversa to chat platforms.

Internal consumers POST normalized outbound messages; we resolve the adapter,
send, persist on success, and return {"data": {...}}.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.adapters.base import BasePlatformAdapter
from app.adapters.telegram import TelegramAdapter
from app.schemas.conversa import Channel, OutboundMessage, OutboundSendResult
from app.services.conversation_event_service import ConversationEventService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outbound", tags=["outbound"])


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


@router.post("", response_model=dict[str, Any])
async def send_outbound(
    body: OutboundMessage,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Send an outbound message to the specified channel.
    Resolve adapter by channel, send, persist on success. Return {"data": { success, platform_message_id? }}.
    """
    adapters = _adapter_registry()
    adapter = adapters.get(body.channel)
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
    service = ConversationEventService(db)
    service.create_event_from_outbound(
        body, platform_message_id=result.platform_message_id
    )
    return {
        "data": {
            "success": True,
            "platform_message_id": result.platform_message_id,
        }
    }
