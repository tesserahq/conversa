"""
Outbound API: send messages via Conversa to chat platforms.

Internal consumers POST normalized outbound messages; we resolve the adapter,
send, persist on success, and return {"data": {...}}.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.commands.outbound import SendOutboundCommand
from app.db import get_db
from app.schemas.conversa import OutboundMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outbound", tags=["outbound"])


@router.post("", response_model=dict[str, Any])
async def send_outbound(
    body: OutboundMessage,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Send an outbound message to the specified channel.
    Resolve adapter by channel, send, persist on success. Return {"data": { success, platform_message_id? }}.
    """
    command = SendOutboundCommand(db)
    return await command.execute(body)
