from datetime import datetime, timezone
import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.channels.envelope import InboundMessage, OutboundMessage
from app.channels.plugins.telegram.config import TelegramConfig


def _inbound_message() -> InboundMessage:
    return InboundMessage(
        channel="telegram",
        account_id="acc-1",
        sender_id="sender-1",
        chat_id="chat-1",
        thread_id=None,
        message_id="msg-1",
        text="hello",
        timestamp=datetime.now(timezone.utc),
        raw={},
    )


def _load_plugin_module(monkeypatch, fake_router):
    fake_app_state_module = types.ModuleType("app.core.app_state")
    fake_app_state_module.state = SimpleNamespace(router=fake_router)
    monkeypatch.setitem(sys.modules, "app.core.app_state", fake_app_state_module)
    monkeypatch.delitem(
        sys.modules, "app.channels.plugins.telegram.plugin", raising=False
    )
    return importlib.import_module("app.channels.plugins.telegram.plugin")


@pytest.mark.asyncio
async def test_handle_inbound_sends_error_when_linked_user_missing(monkeypatch):
    fake_router = SimpleNamespace(
        _linker=SimpleNamespace(get_linked_user=lambda channel, sender_id: None),
        route_to_llm=AsyncMock(),
    )
    telegram_plugin = _load_plugin_module(monkeypatch, fake_router)
    plugin = telegram_plugin.TelegramPlugin(TelegramConfig(bot_token="token"))
    plugin.send = AsyncMock()

    await plugin.handle_inbound(_inbound_message())

    plugin.send.assert_awaited_once()
    sent_msg = plugin.send.await_args.args[0]
    assert isinstance(sent_msg, OutboundMessage)
    assert sent_msg.text == telegram_plugin.LINKED_USER_RESOLUTION_ERROR
    fake_router.route_to_llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_inbound_routes_when_linked_user_exists(monkeypatch):
    linked_user_id = uuid4()
    fake_router = SimpleNamespace(
        _linker=SimpleNamespace(
            get_linked_user=lambda channel, sender_id: SimpleNamespace(
                id=linked_user_id
            )
        ),
        route_to_llm=AsyncMock(
            return_value=OutboundMessage(
                channel="telegram",
                account_id="acc-1",
                chat_id="chat-1",
                thread_id=None,
                text="ok",
                reply_to="msg-1",
                media=[],
            )
        ),
    )
    telegram_plugin = _load_plugin_module(monkeypatch, fake_router)
    plugin = telegram_plugin.TelegramPlugin(TelegramConfig(bot_token="token"))
    plugin.send = AsyncMock()

    inbound = _inbound_message()
    await plugin.handle_inbound(inbound)

    fake_router.route_to_llm.assert_awaited_once_with(inbound, user_id=linked_user_id)
    plugin.send.assert_awaited_once()
