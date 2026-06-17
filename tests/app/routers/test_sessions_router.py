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


def test_list_sessions_with_message_limit_serializes_message_metadata(
    client, db, setup_user
):
    """GET /sessions with message_limit includes recent messages and metadata dict."""
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

    response = client.get("/sessions?message_limit=2")
    assert response.status_code == 200, response.json()

    data = response.json()
    row = next(item for item in data["items"] if item["id"] == str(session.id))
    assert row["message_count"] == 2
    assert row["messages"] is not None
    assert len(row["messages"]) == 2
    assert row["messages"][0]["metadata"] == {"source": "telegram", "message_id": "m-1"}
    assert row["messages"][1]["metadata"] == {"assistant": True}
