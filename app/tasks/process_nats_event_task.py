"""Task for processing NATS events asynchronously."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import ValidationError

from app.config import get_settings
from app.infra.celery_app import celery_app
from app.infra.logging_config import get_logger
from tessera_sdk.events.event import Event
from app.db import db_manager
from app.models.session import Session
import asyncio
from telegram import Bot

from app.schemas.session import MessageCreate
from app.services.session_message_service import SessionMessageService
from app.services.session_service import SessionService

logger = get_logger("nats_event_task")

LINKED_EVENT_TYPE = "com.identies.external_account.linked"
TELEGRAM_CHANNEL = "telegram"
TELEGRAM_LINKED_MESSAGE = "Your account has been linked to your Telegram account!"


async def _send_telegram_linked_message(chat_id: str) -> str:
    """Send account-linked confirmation message to Telegram user."""
    settings = get_settings()
    if not settings.telegram_enabled:
        raise RuntimeError("Telegram notifications are disabled")
    if not settings.telegram_bot_token:
        raise RuntimeError("Telegram bot token is not configured")

    async with Bot(token=settings.telegram_bot_token) as bot:
        sent_message = await bot.send_message(
            chat_id=int(chat_id),
            text=TELEGRAM_LINKED_MESSAGE,
        )
    return str(sent_message.message_id)


def _persist_linked_notification(
    channel: str,
    chat_id: str,
    event: Event,
    provider_message_id: str,
) -> None:
    """Persist outbound linked-account notification in session history."""
    with db_manager.db_session() as db:
        session_service = SessionService(db)
        message_service = SessionMessageService(db)
        session = (
            db.query(Session)
            .filter(Session.channel == channel, Session.chat_id == chat_id)
            .order_by(Session.last_message_at.desc())
            .first()
        )
        if session is None:
            session, _ = session_service.get_or_create_by_key(
                session_key=f"{channel}:{chat_id}",
                defaults={
                    "channel": channel,
                    "chat_id": chat_id,
                    "origin": {"from": chat_id, "to": chat_id},
                },
            )
        message_service.create_message(
            session_id=session.id,
            data=MessageCreate(
                direction="outbound",
                content=TELEGRAM_LINKED_MESSAGE,
                provider_message_id=provider_message_id,
                metadata={
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "system": True,
                },
            ),
        )
        session.last_message_at = datetime.now(timezone.utc)
        db.commit()


def _handle_external_account_linked_event(event: Event) -> None:
    """Handle account-linked event by notifying user and recording session message."""
    external_account = event.event_data.get("external_account", {})
    external_user_id = external_account.get("external_id")
    platform = external_account.get("platform")

    if not external_user_id or not platform:
        logger.warning("Missing external account fields in event: %s", event.id)
        return

    channel = str(platform).lower()
    if channel != TELEGRAM_CHANNEL:
        logger.info(
            "Skipping linked account notification for unsupported channel: %s",
            channel,
        )
        return

    provider_message_id = asyncio.run(
        _send_telegram_linked_message(chat_id=str(external_user_id))
    )
    _persist_linked_notification(
        channel=channel,
        chat_id=str(external_user_id),
        event=event,
        provider_message_id=provider_message_id,
    )
    logger.info(
        "Sent and stored linked notification for channel=%s, chat_id=%s, event_id=%s",
        channel,
        external_user_id,
        event.id,
    )


@celery_app.task(name="app.tasks.process_nats_event_task.process_nats_event_task")
def process_nats_event_task(msg: Dict) -> Optional[str]:
    """
    Process a NATS event message and store it in the database.

    This task runs asynchronously via Celery, allowing the NATS handler
    to quickly acknowledge messages and continue processing.

    Args:
        msg: Dictionary containing the event message from NATS (Tessera Event schema).

    Returns:
        Optional[str]: The event ID as a string, or None on validation error
    """
    try:
        event = Event.model_validate(msg)
    except ValidationError as e:
        logger.warning("Invalid NATS event payload: %s", e)
        return None

    if event.event_type == LINKED_EVENT_TYPE:
        _handle_external_account_linked_event(event)

    return event.id
