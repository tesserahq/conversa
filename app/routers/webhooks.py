"""
Webhook routes for inbound chat platform updates.

Platforms POST raw updates here; we parse, persist, and return 200.
Webhooks are excluded from auth (SKIP_AUTH_PATHS).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.commands.webhooks import TelegramWebhookCommand
from app.db import get_db
from app.schemas.telegram import TelegramWebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    body: TelegramWebhookUpdate,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Receive Telegram webhook updates. Parse, persist inbound event, return 200.
    Validate X-Telegram-Bot-Api-Secret-Token if TELEGRAM_WEBHOOK_SECRET is set.
    """
    command = TelegramWebhookCommand(db)
    return await command.execute(request, body)
