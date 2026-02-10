"""Task for processing NATS events asynchronously."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import ValidationError

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from tessera_sdk.events.event import Event
from app.db import db_manager
from app.commands.outbound.send_outbound_command import SendOutboundCommand
from app.schemas.conversa import OutboundMessage, Channel
import asyncio

logger = get_logger("nats_event_task")


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

    # It means the external account was linked to the user
    # So we need to notify the user
    if event.event_type == "com.identies.external_account.linked":

        external_user_id = event.event_data["external_account"]["external_id"]
        platform = event.event_data["external_account"]["platform"]

        if platform == Channel.TELEGRAM:
            outbound_body = OutboundMessage(
                channel=Channel.TELEGRAM,
                external_user_id=external_user_id,
                text=("Your account has been linked to your Telegram account!"),
            )

            logger.info("Sending outbound message to user: %s", outbound_body)

            with db_manager.db_session() as db:
                send_outbound = SendOutboundCommand(db)
                asyncio.run(send_outbound.execute(outbound_body))

    return event.id
