"""Tests for LLMRunner (Modela integration)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.channels.envelope import InboundMessage
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
        timestamp=datetime.now(timezone.utc),
        raw={},
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
        model_name="test-model",
        system_prompt="Sys",
        modela_audience="modela",
        modela_scopes="modela:chat:complete",
        token_repo=_FakeTokenRepo("token"),
    )
    msg = _inbound("Hello")
    with pytest.raises(ValueError, match="user_id"):
        await runner.run(msg)


@pytest.mark.asyncio
async def test_run_uses_delegated_token_and_modela_complete(monkeypatch):
    user_id = uuid4()
    token_calls: list[dict] = []
    complete_calls: list[dict] = []

    class _TrackingTokenRepo:
        def get_access_token(self, **kwargs):
            token_calls.append(kwargs)
            return "delegated-user-token"

    class _FakeModelaClient:
        def __init__(self, **kwargs):
            complete_calls.append({"init": kwargs})

        def complete(self, **kwargs):
            complete_calls.append({"complete": kwargs})
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="Modela reply"))
                ]
            )

    monkeypatch.setattr(llm_module, "ModelaClient", _FakeModelaClient)

    runner = LLMRunner(
        model_name="gpt-4o-mini",
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
    assert complete_calls[0]["init"]["api_token"] == "delegated-user-token"
    complete = complete_calls[1]["complete"]
    assert complete["model"] == "gpt-4o-mini"
    assert complete["project_id"] == "*"
    assert complete["messages"][0].role == "system"
    assert complete["messages"][-1].role == "user"
    assert complete["messages"][-1].content == "What is up?"


@pytest.mark.asyncio
async def test_run_raises_when_modela_returns_no_choices(monkeypatch):
    class _EmptyModelaClient:
        def __init__(self, **kwargs):
            pass

        def complete(self, **kwargs):
            return SimpleNamespace(choices=[])

    monkeypatch.setattr(llm_module, "ModelaClient", _EmptyModelaClient)

    runner = LLMRunner(
        model_name="m",
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
