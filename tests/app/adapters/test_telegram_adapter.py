"""Tests for TelegramAdapter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.adapters.telegram import TelegramAdapter
from app.schemas.conversa import Channel, OutboundMessage, OutboundSendResult


def minimal_telegram_update():
    """Minimal valid Telegram webhook update (message with text)."""
    return {
        "update_id": 123,
        "message": {
            "message_id": 456,
            "from": {
                "id": 789,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "language_code": "en",
            },
            "chat": {
                "id": 789,
                "type": "private",
                "first_name": "Test",
                "last_name": "User",
            },
            "date": 1609459200,  # Unix timestamp
            "text": "hello",
        },
    }


# Token format: digits:rest (e.g. 123456:ABC). Used only for parse tests; no real API calls.
FAKE_TOKEN = "123456:AAHdqTcvCH1vGWJxfSeofSAs0K5P"


@pytest.fixture
def telegram_adapter():
    return TelegramAdapter(bot_token=FAKE_TOKEN, webhook_secret=None)


def test_verify_webhook_no_secret(telegram_adapter):
    assert telegram_adapter.verify_webhook(None, {}) is True
    assert (
        telegram_adapter.verify_webhook(None, {"X-Telegram-Bot-Api-Secret-Token": "x"})
        is True
    )


def test_verify_webhook_with_secret():
    adapter = TelegramAdapter(bot_token=FAKE_TOKEN, webhook_secret="secret")
    assert (
        adapter.verify_webhook("secret", {"X-Telegram-Bot-Api-Secret-Token": "secret"})
        is True
    )
    assert (
        adapter.verify_webhook("secret", {"X-Telegram-Bot-Api-Secret-Token": "wrong"})
        is False
    )


def test_parse_webhook(telegram_adapter):
    payload = minimal_telegram_update()
    inbound = telegram_adapter.parse_webhook(payload)
    assert inbound.channel == Channel.TELEGRAM
    assert inbound.external_user_id == "789"
    assert inbound.message_id == "456"
    assert inbound.text == "hello"


def test_parse_webhook_no_message_raises(telegram_adapter):
    payload = {"update_id": 123}
    with pytest.raises(ValueError, match="no message"):
        telegram_adapter.parse_webhook(payload)


@pytest.mark.asyncio
async def test_send_returns_result():
    adapter = TelegramAdapter(bot_token=FAKE_TOKEN)
    outbound = OutboundMessage(
        channel=Channel.TELEGRAM,
        external_user_id="123",
        text="hi",
    )
    result = await adapter.send(outbound)
    assert isinstance(result, OutboundSendResult)
    assert result.success is False
