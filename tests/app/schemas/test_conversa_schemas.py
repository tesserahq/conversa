"""Tests for Conversa normalized message schemas."""

from datetime import datetime, timezone


from app.schemas.conversa import (
    Channel,
    InboundMessage,
    MessageMetadata,
    OutboundMessage,
    OutboundSendResult,
)


def test_channel_enum():
    assert Channel.TELEGRAM.value == "telegram"


def test_inbound_message_minimal():
    msg = InboundMessage(
        channel=Channel.TELEGRAM,
        external_user_id="123",
        message_id="456",
        text="hello",
    )
    assert msg.channel == Channel.TELEGRAM
    assert msg.external_user_id == "123"
    assert msg.message_id == "456"
    assert msg.text == "hello"
    assert msg.attachments == []
    assert msg.metadata is not None


def test_inbound_message_with_metadata():
    ts = datetime.now(timezone.utc)
    msg = InboundMessage(
        channel=Channel.TELEGRAM,
        external_user_id="123",
        message_id="456",
        text="hi",
        metadata=MessageMetadata(locale="en", timestamp=ts),
    )
    assert msg.metadata.locale == "en"
    assert msg.metadata.timestamp == ts


def test_outbound_message_minimal():
    msg = OutboundMessage(
        channel=Channel.TELEGRAM,
        external_user_id="123",
        text="reply",
    )
    assert msg.channel == Channel.TELEGRAM
    assert msg.external_user_id == "123"
    assert msg.text == "reply"
    assert msg.reply_to_message_id is None


def test_outbound_send_result():
    r = OutboundSendResult(success=True, platform_message_id="789")
    assert r.success is True
    assert r.platform_message_id == "789"
    r2 = OutboundSendResult(success=False, platform_message_id=None)
    assert r2.success is False
