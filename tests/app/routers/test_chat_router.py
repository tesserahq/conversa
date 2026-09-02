"""Tests for the direct chat API endpoint (POST /chat/completions)."""

from uuid import uuid4

from app.routers.chat_router import get_router


class _FakeOutbound:
    def __init__(self, text: str, chat_id: str = "api-chat-1"):
        self.text = text
        self.chat_id = chat_id


class _FakeRouter:
    def __init__(self, reply_text: str = "Hi there", session_id=None):
        self.reply_text = reply_text
        self.session_id = session_id or uuid4()
        self.calls: list[dict] = []

    async def route_api_message(self, *, user_id, user_content, session_id=None):
        self.calls.append(
            {
                "user_id": user_id,
                "user_content": user_content,
                "session_id": session_id,
            }
        )
        return _FakeOutbound(self.reply_text), self.session_id


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


def test_create_chat_completion_rejects_stream_true(client, setup_user):
    fake_router = _FakeRouter()
    client.app.dependency_overrides[get_router] = lambda: fake_router

    response = client.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "Hi"}], "stream": True},
    )

    assert response.status_code == 422
    assert fake_router.calls == []


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
