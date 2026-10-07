"""Tests for LLMRunner (Modela integration)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from tessera_sdk.clients.modela import ModelaServerError
from tessera_sdk.infra.events import Event
from tessera_sdk.mcp import CompletionInclude, TruncationMarker

from app.channels.envelope import InboundMessage
from app.core.completion_output import (
    CompletionEvent,
    CompletionFailure,
    CompletionTextDelta,
    CompletionTruncation,
)
from app.workers import llm as llm_module
from app.workers.llm import LLMRunner, _build_completion_messages


def _inbound(text: str) -> InboundMessage:
    return InboundMessage(
        channel="telegram",
        account_id="acc",
        sender_id="sender",
        chat_id="chat",
        thread_id=None,
        message_id="msg-1",
        text=text,
        timestamp=datetime.now(UTC),
        raw={},
    )


def _chunk(content: str | None = None, finish_reason: str | None = None):
    return SimpleNamespace(
        extensions=None,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
    )


def _event(event_id: str = "evt-1") -> Event:
    return Event(
        id=event_id,
        source="/linden/persons",
        event_type="person.created",
        time="2026-10-07T10:00:00Z",
        tags=["origin:mcp"],
        event_data={"resource": {"type": "person", "id": "person-1"}},
    )


def _extension_chunk(*, event=None, truncation=None):
    return SimpleNamespace(
        choices=[],
        extensions=SimpleNamespace(
            event=event,
            truncation=truncation,
            tool_execution=None,
        ),
    )


def test_build_completion_messages_ordering_and_roles():
    messages = _build_completion_messages(
        system_prompt="You are helpful.",
        history=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "system", "content": "Summary from compact"},
        ],
        user_content="Next question",
        context={"facts": {"name": "Ada"}},
    )
    assert len(messages) == 5
    assert messages[0].role == "system"
    assert "You are helpful." in messages[0].content
    assert "Facts:" in messages[0].content
    assert messages[1].role == "user" and messages[1].content == "Hi"
    assert messages[2].role == "assistant" and messages[2].content == "Hello"
    assert (
        messages[3].role == "system" and messages[3].content == "Summary from compact"
    )
    assert messages[4].role == "user" and messages[4].content == "Next question"


def test_build_completion_messages_includes_client_context():
    messages = _build_completion_messages(
        system_prompt="You are helpful.",
        history=[],
        user_content="Create a todo list",
        client_context={"account_id": "acc-1", "todo_list_id": "list-1"},
    )
    assert messages[0].role == "system"
    assert "Current app context" in messages[0].content
    assert "acc-1" in messages[0].content
    assert "list-1" in messages[0].content


def test_build_completion_messages_skips_empty_content():
    messages = _build_completion_messages(
        system_prompt="Sys",
        history=[{"role": "user", "content": "  "}],
        user_content="",
    )
    assert len(messages) == 1
    assert messages[0].role == "system"


@pytest.mark.asyncio
async def test_run_requires_user_id():
    runner = LLMRunner(
        system_prompt="Sys",
        modela_audience="modela",
        modela_scopes="modela:chat:complete",
        token_repo=_FakeTokenRepo("token"),
    )
    msg = _inbound("Hello")
    with pytest.raises(ValueError, match="user_id"):
        await runner.run(msg)


@pytest.mark.asyncio
async def test_stream_requires_user_id():
    runner = LLMRunner(
        system_prompt="Sys",
        modela_audience="modela",
        modela_scopes="modela:chat:complete",
        token_repo=_FakeTokenRepo("token"),
    )
    msg = _inbound("Hello")
    with pytest.raises(ValueError, match="user_id"):
        async for _ in runner.stream(msg):
            pass


@pytest.mark.asyncio
async def test_run_uses_delegated_token_and_joins_stream_deltas(monkeypatch):
    user_id = uuid4()
    token_calls: list[dict] = []
    stream_calls: list[dict] = []

    class _TrackingTokenRepo:
        def get_access_token(self, **kwargs):
            token_calls.append(kwargs)
            return "delegated-user-token"

    class _FakeModelaClient:
        def __init__(self, **kwargs):
            stream_calls.append({"init": kwargs})

        async def stream_complete(self, **kwargs):
            stream_calls.append({"stream_complete": kwargs})
            for content in ("Modela ", "reply"):
                yield _chunk(content=content)
            yield _chunk(finish_reason="stop")

    monkeypatch.setattr(llm_module, "ModelaClient", _FakeModelaClient)

    runner = LLMRunner(
        system_prompt="Be concise.",
        modela_audience="modela",
        modela_scopes="modela:chat:complete",
        token_repo=_TrackingTokenRepo(),
    )
    msg = _inbound("What is up?")
    reply = await runner.run(
        msg,
        history=[{"role": "assistant", "content": "Hi there"}],
        user_id=user_id,
    )

    assert reply == "Modela reply"
    assert token_calls == [
        {
            "user_id": user_id,
            "audience": "modela",
            "scopes": "modela:chat:complete",
        }
    ]
    assert stream_calls[0]["init"]["api_token"] == "delegated-user-token"
    assert stream_calls[0]["init"]["timeout"] == 10
    stream_complete = stream_calls[1]["stream_complete"]
    assert stream_complete["project_id"] == "*"
    assert "include" not in stream_complete
    assert "model" not in stream_complete
    assert stream_complete["messages"][0].role == "system"
    assert stream_complete["messages"][-1].role == "user"
    assert stream_complete["messages"][-1].content == "What is up?"


@pytest.mark.asyncio
async def test_stream_yields_deltas_in_order(monkeypatch):
    class _FakeModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            for content in ("Hel", "lo"):
                yield _chunk(content=content)
            yield _chunk(finish_reason="stop")

    monkeypatch.setattr(llm_module, "ModelaClient", _FakeModelaClient)

    runner = LLMRunner(
        system_prompt="s",
        modela_audience="modela",
        modela_scopes="scope",
        token_repo=_FakeTokenRepo("t"),
    )
    msg = _inbound("hi")
    deltas = [d async for d in runner.stream(msg, user_id=uuid4())]

    assert deltas == [CompletionTextDelta("Hel"), CompletionTextDelta("lo")]


@pytest.mark.asyncio
async def test_stream_requests_and_yields_only_event_channel_metadata(monkeypatch):
    event = _event()
    marker = TruncationMarker(
        channel=CompletionInclude.EVENTS,
        dropped_count=2,
    )
    stream_calls = []

    class _FakeModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            stream_calls.append(kwargs)
            yield _chunk(content="Created. ")
            yield _extension_chunk(event=event)
            yield _extension_chunk(truncation=marker)

    monkeypatch.setattr(llm_module, "ModelaClient", _FakeModelaClient)
    runner = LLMRunner(
        system_prompt="s",
        modela_audience="modela",
        modela_scopes="scope",
        token_repo=_FakeTokenRepo("t"),
    )

    items = [
        item
        async for item in runner.stream(
            _inbound("create"), user_id=uuid4(), include_events=True
        )
    ]

    assert stream_calls[0]["include"] == [CompletionInclude.EVENTS]
    assert items == [
        CompletionTextDelta("Created. "),
        CompletionEvent(event),
        CompletionTruncation(marker),
    ]


@pytest.mark.asyncio
async def test_collect_preserves_inline_and_error_response_events(monkeypatch):
    inline_event = _event("event-inline")
    error_event = _event("event-error")
    marker = TruncationMarker(channel=CompletionInclude.EVENTS, dropped_count=1)

    class _FailingModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            yield _extension_chunk(event=inline_event)
            raise ModelaServerError(
                "upstream failed",
                status_code=502,
                events=(inline_event, error_event),
                truncations=(marker,),
            )

    monkeypatch.setattr(llm_module, "ModelaClient", _FailingModelaClient)
    runner = LLMRunner(
        system_prompt="s",
        modela_audience="modela",
        modela_scopes="scope",
        token_repo=_FakeTokenRepo("t"),
    )

    with pytest.raises(CompletionFailure) as failure:
        await runner.collect(_inbound("create"), user_id=uuid4(), include_events=True)

    assert failure.value.original_error.status_code == 502
    assert failure.value.events == (inline_event, error_event)
    assert failure.value.truncations == (marker,)


def _runner_with_client(monkeypatch, client_cls) -> LLMRunner:
    monkeypatch.setattr(llm_module, "ModelaClient", client_cls)
    return LLMRunner(
        system_prompt="s",
        modela_audience="modela",
        modela_scopes="scope",
        token_repo=_FakeTokenRepo("t"),
    )


@pytest.mark.asyncio
async def test_stream_yields_error_body_events_before_raising(monkeypatch):
    error_event = _event("event-error")

    class _FailingModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            raise ModelaServerError(
                "upstream failed", status_code=500, events=(error_event,)
            )
            yield  # pragma: no cover - makes this an async generator

    runner = _runner_with_client(monkeypatch, _FailingModelaClient)
    items = []
    with pytest.raises(ModelaServerError):
        async for item in runner.stream(
            _inbound("create"), user_id=uuid4(), include_events=True
        ):
            items.append(item)

    assert items == [CompletionEvent(error_event)]


@pytest.mark.asyncio
async def test_stream_deduplicates_error_body_events_without_wire_id(monkeypatch):
    payload = {
        "source": "/linden/persons",
        "event_type": "person.created",
        "time": "2026-10-07T10:00:00Z",
    }
    inline_event = Event(**payload)
    error_copy = Event(**payload)
    assert inline_event.id != error_copy.id

    class _FailingModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            yield _extension_chunk(event=inline_event)
            raise ModelaServerError(
                "upstream failed", status_code=500, events=(error_copy,)
            )

    runner = _runner_with_client(monkeypatch, _FailingModelaClient)

    with pytest.raises(CompletionFailure) as failure:
        await runner.collect(_inbound("create"), user_id=uuid4(), include_events=True)

    assert failure.value.events == (inline_event,)


@pytest.mark.asyncio
async def test_collect_reraises_original_error_when_no_events_observed(monkeypatch):
    class _FailingModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            raise ModelaServerError("upstream failed", status_code=500)
            yield  # pragma: no cover - makes this an async generator

    runner = _runner_with_client(monkeypatch, _FailingModelaClient)

    with pytest.raises(ModelaServerError):
        await runner.collect(_inbound("create"), user_id=uuid4(), include_events=True)


@pytest.mark.asyncio
async def test_run_raises_when_modela_stream_is_empty(monkeypatch):
    class _EmptyModelaClient:
        def __init__(self, **kwargs):
            pass

        async def stream_complete(self, **kwargs):
            return
            yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(llm_module, "ModelaClient", _EmptyModelaClient)

    runner = LLMRunner(
        system_prompt="s",
        modela_audience="modela",
        modela_scopes="scope",
        token_repo=_FakeTokenRepo("t"),
    )
    msg = _inbound("x")
    with pytest.raises(ValueError, match="no completion choices"):
        await runner.run(msg, user_id=uuid4())


class _FakeTokenRepo:
    def __init__(self, token: str) -> None:
        self._token = token

    def get_access_token(self, **kwargs):
        return self._token
