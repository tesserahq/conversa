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


class _FakeLLMEcho:
    async def run(self, *_args, **kwargs):
        return "assistant reply"

    async def stream(self, *_args, **kwargs):
        for delta in ("assistant ", "reply"):
            yield delta


class _FakeSessionManagerForApi:
    created_calls: list = []
    add_turn_calls: list = []

    def __init__(self, db):
        self._db = db

    def get_or_create_session(self, msg, user_id):
        self.created_calls.append({"msg": msg, "user_id": user_id})
        return SimpleNamespace(id="new-session", user_id=user_id, chat_id=msg.chat_id)

    def get_history_for_llm(self, _session_id, limit=50):
        return []

    def add_turn(self, session_id, _msg, _outbound):
        self.add_turn_calls.append(session_id)


@pytest.mark.asyncio
async def test_route_api_message_creates_new_session_when_no_session_id(monkeypatch):
    user_id = uuid4()

    @contextmanager
    def _fake_db_session():
        yield object()

    fake_manager = _FakeSessionManagerForApi
    fake_manager.created_calls = []
    fake_manager.add_turn_calls = []

    router = routing.Router(llm=_FakeLLMEcho())
    monkeypatch.setattr(routing, "db_session", _fake_db_session)
    monkeypatch.setattr(routing, "SessionManager", fake_manager)
    monkeypatch.setattr(router, "_load_context_for_user", lambda db, user_id: None)

    outbound, session_id = await router.route_api_message(
        user_id=user_id, user_content="Hello there"
    )

    assert outbound.text == "assistant reply"
    assert outbound.channel == routing.API_CHANNEL
    assert session_id == "new-session"
    assert fake_manager.created_calls[0]["user_id"] == user_id
    assert fake_manager.created_calls[0]["msg"].text == "Hello there"
    assert fake_manager.add_turn_calls == ["new-session"]


@pytest.mark.asyncio
async def test_route_api_message_reuses_owned_session(monkeypatch):
    user_id = uuid4()
    existing_session_id = uuid4()

    @contextmanager
    def _fake_db_session():
        yield object()

    class _FakeSessionRepo:
        def __init__(self, db):
            pass

        def get_session(self, session_id):
            assert session_id == existing_session_id
            return SimpleNamespace(
                id=existing_session_id, user_id=user_id, chat_id="existing-chat"
            )

    fake_manager = _FakeSessionManagerForApi
    fake_manager.created_calls = []
    fake_manager.add_turn_calls = []

    router = routing.Router(llm=_FakeLLMEcho())
    monkeypatch.setattr(routing, "db_session", _fake_db_session)
    monkeypatch.setattr(routing, "SessionManager", fake_manager)
    monkeypatch.setattr(routing, "SessionRepository", _FakeSessionRepo)
    monkeypatch.setattr(router, "_load_context_for_user", lambda db, user_id: None)

    outbound, session_id = await router.route_api_message(
        user_id=user_id, user_content="Follow up", session_id=existing_session_id
    )

    assert session_id == existing_session_id
    assert outbound.chat_id == "existing-chat"
    # No new session was created since the existing one was reused.
    assert fake_manager.created_calls == []
    assert fake_manager.add_turn_calls == [existing_session_id]


@pytest.mark.asyncio
async def test_route_api_message_ignores_session_owned_by_another_user(monkeypatch):
    user_id = uuid4()
    other_users_session_id = uuid4()

    @contextmanager
    def _fake_db_session():
        yield object()

    class _FakeSessionRepo:
        def __init__(self, db):
            pass

        def get_session(self, session_id):
            return SimpleNamespace(
                id=other_users_session_id, user_id=uuid4(), chat_id="not-yours"
            )

    fake_manager = _FakeSessionManagerForApi
    fake_manager.created_calls = []
    fake_manager.add_turn_calls = []

    router = routing.Router(llm=_FakeLLMEcho())
    monkeypatch.setattr(routing, "db_session", _fake_db_session)
    monkeypatch.setattr(routing, "SessionManager", fake_manager)
    monkeypatch.setattr(routing, "SessionRepository", _FakeSessionRepo)
    monkeypatch.setattr(router, "_load_context_for_user", lambda db, user_id: None)

    outbound, session_id = await router.route_api_message(
        user_id=user_id, user_content="Hi", session_id=other_users_session_id
    )

    # A session_id belonging to someone else is treated as not found: a new
    # session is created instead of reusing (or leaking) the other user's.
    assert session_id == "new-session"
    assert len(fake_manager.created_calls) == 1


@pytest.mark.asyncio
async def test_stream_api_message_yields_deltas_and_persists_on_completion(
    monkeypatch,
):
    user_id = uuid4()

    @contextmanager
    def _fake_db_session():
        yield object()

    fake_manager = _FakeSessionManagerForApi
    fake_manager.created_calls = []
    fake_manager.add_turn_calls = []

    router = routing.Router(llm=_FakeLLMEcho())
    monkeypatch.setattr(routing, "db_session", _fake_db_session)
    monkeypatch.setattr(routing, "SessionManager", fake_manager)
    monkeypatch.setattr(router, "_load_context_for_user", lambda db, user_id: None)

    session_id, delta_gen = await router.stream_api_message(
        user_id=user_id, user_content="Hello there"
    )

    # Session is resolved up front, before any deltas are consumed.
    assert session_id == "new-session"
    assert fake_manager.add_turn_calls == []

    deltas = [d async for d in delta_gen]

    assert deltas == ["assistant ", "reply"]
    # Persisted only once the generator is fully drained.
    assert fake_manager.add_turn_calls == ["new-session"]


@pytest.mark.asyncio
async def test_stream_api_message_does_not_persist_if_generator_not_drained(
    monkeypatch,
):
    """Happy-path-only scope for this method: if the caller stops consuming
    the generator early (e.g. a dropped connection), nothing is persisted.
    Disconnect-safe persistence is a separate follow-up (tesserahq/conversa#66).
    """
    user_id = uuid4()

    @contextmanager
    def _fake_db_session():
        yield object()

    fake_manager = _FakeSessionManagerForApi
    fake_manager.created_calls = []
    fake_manager.add_turn_calls = []

    router = routing.Router(llm=_FakeLLMEcho())
    monkeypatch.setattr(routing, "db_session", _fake_db_session)
    monkeypatch.setattr(routing, "SessionManager", fake_manager)
    monkeypatch.setattr(router, "_load_context_for_user", lambda db, user_id: None)

    _session_id, delta_gen = await router.stream_api_message(
        user_id=user_id, user_content="Hello there"
    )

    await delta_gen.__anext__()  # consume only the first delta
    await delta_gen.aclose()

    assert fake_manager.add_turn_calls == []
