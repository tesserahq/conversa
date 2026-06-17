"""Tests for sessions router."""

from datetime import datetime, timezone

from app.models.session import Session
from app.models.session_message import SessionMessage


def test_list_sessions_returns_paginated_items(client, db, setup_user):
    """GET /sessions returns a paginated list of sessions."""
    session = Session(
        session_key="telegram:chat-1",
        user_id=setup_user.id,
        channel="telegram",
        chat_id="chat-1",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()

    response = client.get("/sessions")
    assert response.status_code == 200, response.json()

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert any(item["session_key"] == "telegram:chat-1" for item in data["items"])


def test_list_sessions_does_not_embed_messages(client, db, setup_user):
    """GET /sessions should not embed message previews."""
    session = Session(
        session_key="telegram:chat-2",
        user_id=setup_user.id,
        channel="telegram",
        chat_id="chat-2",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    inbound = SessionMessage(
        session_id=session.id,
        direction="inbound",
        content="hello",
        extra={"source": "telegram", "message_id": "m-1"},
    )
    outbound = SessionMessage(
        session_id=session.id,
        direction="outbound",
        content="hi",
        extra={"assistant": True},
    )
    db.add_all([inbound, outbound])
    db.commit()

    response = client.get("/sessions")
    assert response.status_code == 200, response.json()

    data = response.json()
    row = next(item for item in data["items"] if item["id"] == str(session.id))
    assert row["message_count"] is None
    assert row["messages"] is None


def test_list_session_messages_returns_paginated_messages(client, db, setup_user):
    """GET /sessions/{id}/messages returns paginated messages."""
    session = Session(
        session_key="telegram:chat-3",
        user_id=setup_user.id,
        channel="telegram",
        chat_id="chat-3",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()

    db.refresh(session)

    inbound = SessionMessage(
        session_id=session.id,
        direction="inbound",
        content="hello",
        # extra omitted => None
    )
    outbound = SessionMessage(
        session_id=session.id,
        direction="outbound",
        content="hi",
        # extra omitted => None
    )
    db.add_all([inbound, outbound])
    db.commit()

    response = client.get(f"/sessions/{session.id}/messages")
    assert response.status_code == 200, response.json()

    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2
    assert data["items"][0]["direction"] == "inbound"
    assert data["items"][0]["metadata"] is None
    assert data["items"][1]["direction"] == "outbound"
    assert data["items"][1]["metadata"] is None


def test_list_session_messages_returns_404_for_unknown_session(client):
    """GET /sessions/{id}/messages returns 404 for unknown session."""
    from uuid import uuid4

    response = client.get(f"/sessions/{uuid4()}/messages")
    assert response.status_code == 404
