"""
Webhook routes for inbound chat platform updates.

Platforms POST raw updates here; we parse, persist, and return 200.
Webhooks are excluded from auth (SKIP_AUTH_PATHS).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.adapters.telegram import TelegramAdapter
from app.services.conversation_event_service import ConversationEventService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_telegram_adapter() -> TelegramAdapter | None:
    settings = get_settings()
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        return None
    return TelegramAdapter(
        bot_token=settings.telegram_bot_token,
        webhook_secret=settings.telegram_webhook_secret,
    )


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Receive Telegram webhook updates. Parse, persist inbound event, return 200.
    Validate X-Telegram-Bot-Api-Secret-Token if TELEGRAM_WEBHOOK_SECRET is set.
    """
    adapter = _get_telegram_adapter()
    if adapter is None:
        raise HTTPException(
            status_code=503,
            detail="Telegram integration is not configured or disabled",
        )
    settings = get_settings()
    print(f"Telegram webhook secret: {settings.telegram_webhook_secret}")
    print(f"Headers: {request.headers}")
    headers = dict(request.headers) if request.headers else {}
    if not adapter.verify_webhook(settings.telegram_webhook_secret, headers):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Telegram webhook invalid JSON: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    try:
        inbound = adapter.parse_webhook(body)
    except (ValueError, KeyError, TypeError) as e:
        logger.warning("Telegram webhook parse error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from e
    service = ConversationEventService(db)
    service.create_event_from_inbound(inbound)
    return {"status": "ok"}
