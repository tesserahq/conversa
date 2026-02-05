"""Tests for ConversationEventService."""

import pytest
from sqlalchemy.orm import Session

from app.schemas.conversa import (
    Channel,
    InboundMessage,
    MessageMetadata,
    OutboundMessage,
)
from app.services.conversation_event_service import ConversationEventService


@pytest.fixture
def inbound_message():
    return InboundMessage(
        channel=Channel.TELEGRAM,
        external_user_id="123",
        message_id="456",
        text="hello",
        metadata=MessageMetadata(locale="en"),
    )


@pytest.fixture
def outbound_message():
    return OutboundMessage(
        channel=Channel.TELEGRAM,
        external_user_id="123",
        text="reply",
    )


def test_create_event_from_inbound(db: Session, inbound_message: InboundMessage):
    service = ConversationEventService(db)
    event = service.create_event_from_inbound(inbound_message)
    assert event.id is not None
    assert event.direction == "inbound"
    assert event.channel == "telegram"
    assert event.external_user_id == "123"
    assert event.message_id == "456"
    assert event.text == "hello"
    assert event.created_at is not None


def test_create_event_from_outbound(db: Session, outbound_message: OutboundMessage):
    service = ConversationEventService(db)
    event = service.create_event_from_outbound(
        outbound_message, platform_message_id="999"
    )
    assert event.id is not None
    assert event.direction == "outbound"
    assert event.channel == "telegram"
    assert event.external_user_id == "123"
    assert event.text == "reply"
    assert event.platform_message_id == "999"
    assert event.created_at is not None


def test_get_conversation_events(db: Session, inbound_message: InboundMessage):
    service = ConversationEventService(db)
    service.create_event_from_inbound(inbound_message)
    events = service.get_conversation_events(channel="telegram", external_user_id="123")
    assert len(events) == 1
    assert events[0].text == "hello"
