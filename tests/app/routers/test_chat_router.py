"""Tests for the direct chat API endpoint (POST /chat/completions)."""

import json
from uuid import uuid4

from tessera_sdk.clients.modela import ModelaServerError
from tessera_sdk.infra.events import Event

from app.core.completion_output import (
    CompletionEvent,
    CompletionFailure,
    CompletionResult,
    CompletionTextDelta,
)
from app.routers.chat_router import get_router


class _FakeOutbound:
    def __init__(self, text: str, chat_id: str = "api-chat-1"):
        self.text = text
        self.chat_id = chat_id


class _FakeRouter:
    def __init__(self, reply_text: str = "Hi there", session_id=None, deltas=None):
        self.reply_text = reply_text
        self.session_id = session_id or uuid4()
        self.deltas = deltas if deltas is not None else ["Hi ", "there"]
        self.calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def route_api_completion(
        self,
        *,
        user_id,
        user_content,
        session_id=None,
        project_id="*",
        client_context=None,
        include_events=False,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "user_content": user_content,
                "session_id": session_id,
                "project_id": project_id,
                "client_context": client_context,
                "include_events": include_events,
            }
        )
        events = tuple(
            item.event for item in self.deltas if isinstance(item, CompletionEvent)
        )
        return (
            _FakeOutbound(self.reply_text),
            self.session_id,
            CompletionResult(text=self.reply_text, events=events),
        )

    async def stream_api_message(
        self,
        *,
        user_id,
        user_content,
        session_id=None,
        project_id="*",
        client_context=None,
        include_events=False,
    ):
        self.stream_calls.append(
            {
                "user_id": user_id,
                "user_content": user_content,
                "session_id": session_id,
                "project_id": project_id,
                "client_context": client_context,
                "include_events": include_events,
            }
        )

        async def _gen():
            for delta in self.deltas:
                yield (CompletionTextDelta(delta) if isinstance(delta, str) else delta)

        return self.session_id, _gen()


def test_create_chat_completion_returns_assistant_reply(client, setup_user):
    fake_router = _FakeRouter(reply_text="Hello!")
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["choices"][0]["message"]["content"] == "Hello!"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert response.headers["X-Conversa-Session-Id"] == str(fake_router.session_id)
    assert fake_router.calls[0]["user_id"] == setup_user.id
    assert fake_router.calls[0]["user_content"] == "Hi"
    assert fake_router.calls[0]["session_id"] is None
    assert fake_router.calls[0]["include_events"] is False
    assert "extensions" not in data


def test_create_chat_completion_uses_only_the_last_message(client, setup_user):
    fake_router = _FakeRouter()
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply"},
                {"role": "user", "content": "second"},
            ]
        },
    )

    assert response.status_code == 200, response.json()
    assert fake_router.calls[0]["user_content"] == "second"


def test_create_chat_completion_passes_through_session_id(client, setup_user):
    fake_router = _FakeRouter()
    client.app.dependency_overrides[get_router] = lambda: fake_router
    existing_session_id = uuid4()

    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session_id": str(existing_session_id),
        },
    )

    assert response.status_code == 200, response.json()
    assert fake_router.calls[0]["session_id"] == existing_session_id


def test_create_chat_completion_streams_sse_chunks(client, setup_user):
    fake_router = _FakeRouter(deltas=["Hel", "lo"])
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "Hi"}], "stream": True},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["X-Conversa-Session-Id"] == str(fake_router.session_id)

    events = [
        line[len("data: ") :]
        for line in response.text.split("\n\n")
        if line.startswith("data: ")
    ]
    assert events[-1] == "[DONE]"

    data_events = [json.loads(e) for e in events[:-1]]
    contents = [
        c["choices"][0]["delta"].get("content")
        for c in data_events
        if c["choices"][0]["delta"].get("content")
    ]
    assert contents == ["Hel", "lo"]
    assert data_events[0]["choices"][0]["delta"]["role"] == "assistant"
    assert data_events[-1]["choices"][0]["finish_reason"] == "stop"

    assert fake_router.calls == []  # non-streaming path wasn't used
    assert fake_router.stream_calls[0]["user_content"] == "Hi"
    assert fake_router.stream_calls[0]["include_events"] is False


def test_create_chat_completion_streams_events_in_generation_order(client, setup_user):
    event = Event(
        id="event-1",
        source="/linden/persons",
        event_type="person.created",
        time="2026-10-07T10:00:00Z",
        tags=["origin:mcp"],
        event_data={"resource": {"type": "person", "id": "person-1"}},
    )
    fake_router = _FakeRouter(
        deltas=["Created ", CompletionEvent(event), "the person."]
    )
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Create a person"}],
            "stream": True,
            "include": ["events"],
        },
    )

    assert response.status_code == 200, response.text
    chunks = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.split("\n\n")
        if line.startswith("data: {")
    ]
    assert chunks[0]["choices"][0]["delta"]["content"] == "Created "
    assert chunks[1]["choices"] == []
    assert chunks[1]["extensions"]["event"]["id"] == "event-1"
    assert chunks[2]["choices"][0]["delta"]["content"] == "the person."
    assert all("tool_execution" not in chunk.get("extensions", {}) for chunk in chunks)
    assert fake_router.stream_calls[0]["include_events"] is True


def test_create_chat_completion_returns_events_when_requested(client, setup_user):
    event = Event(
        id="event-1",
        source="/linden/persons",
        event_type="person.created",
        time="2026-10-07T10:00:00Z",
        tags=["origin:mcp"],
        event_data={"resource": {"type": "person", "id": "person-1"}},
    )
    fake_router = _FakeRouter(
        reply_text="Created the person.", deltas=[CompletionEvent(event)]
    )
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Create a person"}],
            "include": ["events"],
        },
    )

    assert response.status_code == 200, response.json()
    assert response.json()["extensions"]["events"][0]["id"] == "event-1"
    assert "tool_executions" not in response.json()["extensions"]
    assert fake_router.calls[0]["include_events"] is True


def test_create_chat_completion_preserves_events_on_modela_failure(client, setup_user):
    event = Event(
        id="event-1",
        source="/linden/persons",
        event_type="person.created",
        time="2026-10-07T10:00:00Z",
        tags=["origin:mcp"],
        event_data={"resource": {"type": "person", "id": "person-1"}},
    )

    class _FailingRouter(_FakeRouter):
        async def route_api_completion(self, **kwargs):
            raise CompletionFailure(
                ModelaServerError("upstream failed", status_code=502),
                events=(event,),
            )

    client.app.dependency_overrides[get_router] = _FailingRouter

    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Create a person"}],
            "include": ["events"],
        },
    )

    assert response.status_code == 502
    assert response.json()["extensions"]["events"][0]["id"] == "event-1"
    assert "tool_executions" not in response.json()["extensions"]


def test_create_chat_completion_rejects_tool_execution_channel(client, setup_user):
    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "include": ["tool_executions"],
        },
    )

    assert response.status_code == 422


def test_create_chat_completion_rejects_empty_messages(client, setup_user):
    response = client.post("/chat/completions", json={"messages": []})

    assert response.status_code == 422


def test_create_chat_completion_ignores_model_field(client, setup_user):
    """`model` isn't part of the schema; passing it is silently ignored, not an error."""
    fake_router = _FakeRouter()
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "model": "gpt-4o",
        },
    )

    assert response.status_code == 200, response.json()
