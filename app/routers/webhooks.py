"""Webhook endpoints (e.g. Telegram)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhooks_router.post("/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Handle incoming Telegram webhook updates."""
    telegram = getattr(request.app.state, "telegram", None)
    if telegram is None:
        raise HTTPException(status_code=503, detail="Telegram plugin not ready")
    payload = await request.json()
    await telegram.process_webhook_update(payload)
    return {"status": "ok"}
