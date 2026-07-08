"""Tests for message routing."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import app.core.routing as routing
import pytest
from app.channels.envelope import InboundMessage


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


def test_link_url_format_substitutes_channel_and_link_token(monkeypatch):
    """link_url template placeholders {channel} and {link_token} are filled (routing.py)."""
    monkeypatch.setattr(
        routing,
        "get_settings",
        lambda: SimpleNamespace(
            link_url="https://app.example/link/{channel}/{link_token}",
        ),
    )
    link_token = "tok-abc"
    msg_channel = "telegram"
    link_url = routing.get_settings().link_url.format(
        channel=msg_channel, link_token=link_token
    )
    assert link_url == "https://app.example/link/telegram/tok-abc"


@pytest.mark.asyncio
async def test_route_to_llm_returns_link_message_when_unlinked(monkeypatch):
    msg = _inbound_message()
    router = routing.Router(llm=SimpleNamespace())
    router._linker = SimpleNamespace(
        get_or_resolve_linked_user=lambda channel, external_id: None,
        generate_link_token=lambda channel, external_id: "tok-123",
    )
    monkeypatch.setattr(
        routing,
        "get_settings",
        lambda: SimpleNamespace(
            link_url="https://app.example/link/{channel}/{link_token}"
        ),
    )

    outbound = await router.route_to_llm(msg, user_id=None)

    assert outbound.text is not None
    assert "https://app.example/link/telegram/tok-123" in outbound.text


@pytest.mark.asyncio
async def test_route_to_llm_resolves_user_and_calls_llm(monkeypatch):
    msg = _inbound_message()
    resolved_user_id = uuid4()
    llm_calls: list[dict] = []

    class _FakeLLM:
        async def run(self, *_args, **kwargs):
            llm_calls.append(kwargs)
            return "assistant reply"

    class _FakeSessionManager:
        def __init__(self, db):
            self._db = db

        def get_or_create_session(self, _msg, user_id):
            return SimpleNamespace(id="session-1", user_id=user_id)

        def get_history_for_llm(self, _session_id, limit=50):
            return []

        def add_turn(self, _session_id, _msg, _outbound):
            return None

    @contextmanager
    def _fake_db_session():
        yield object()

    router = routing.Router(llm=_FakeLLM())
    router._linker = SimpleNamespace(
        get_or_resolve_linked_user=lambda channel, external_id: SimpleNamespace(
            id=resolved_user_id
        )
    )
    monkeypatch.setattr(routing, "db_session", _fake_db_session)
    monkeypatch.setattr(routing, "SessionManager", _FakeSessionManager)
    monkeypatch.setattr(router, "_load_context_for_user", lambda db, user_id: None)

    outbound = await router.route_to_llm(msg, user_id=None)

    assert outbound.text == "assistant reply"
    assert llm_calls[0]["user_id"] == resolved_user_id
