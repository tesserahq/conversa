"""
Service for persisting conversation events (inbound/outbound).

Events are immutable; only insert. No update/delete of event content.
"""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.conversation_event import ConversationEvent
from app.schemas.conversa import InboundMessage, OutboundMessage


class ConversationEventService:
    """Create and read conversation events. No update/delete (immutable)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_event_from_inbound(self, inbound: InboundMessage) -> ConversationEvent:
        """Persist an inbound message as a conversation event."""
        event = ConversationEvent(
            direction="inbound",
            channel=inbound.channel.value,
            external_user_id=inbound.external_user_id,
            message_id=inbound.message_id,
            text=inbound.text or None,
            attachments=inbound.attachments or [],
            metadata_=(
                inbound.metadata.model_dump(mode="json") if inbound.metadata else {}
            ),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def create_event_from_outbound(
        self,
        outbound: OutboundMessage,
        platform_message_id: Optional[str] = None,
    ) -> ConversationEvent:
        """Persist an outbound message as a conversation event."""
        event = ConversationEvent(
            direction="outbound",
            channel=outbound.channel.value,
            external_user_id=outbound.external_user_id,
            message_id=outbound.reply_to_message_id,
            text=outbound.text or None,
            attachments=outbound.attachments or [],
            metadata_={},
            platform_message_id=platform_message_id,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_conversation_event(self, event_id: UUID) -> Optional[ConversationEvent]:
        """Fetch a single conversation event by ID."""
        return (
            self.db.query(ConversationEvent)
            .filter(ConversationEvent.id == event_id)
            .first()
        )

    def get_conversation_events(
        self,
        channel: Optional[str] = None,
        external_user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ConversationEvent]:
        """Fetch conversation events, optionally filtered by channel and user. Ordered by created_at."""
        q = self.db.query(ConversationEvent).order_by(
            ConversationEvent.created_at.asc()
        )
        if channel is not None:
            q = q.filter(ConversationEvent.channel == channel)
        if external_user_id is not None:
            q = q.filter(ConversationEvent.external_user_id == external_user_id)
        return q.offset(skip).limit(limit).all()
