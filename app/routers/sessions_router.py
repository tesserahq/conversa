"""Sessions API: list, get, messages, reset, compact."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.session import MessageRead, SessionListRow, SessionRead
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService

sessions_router = APIRouter(prefix="/sessions", tags=["Session"])


@sessions_router.get("", response_model=dict)
def list_sessions(
    channel: str | None = Query(None),
    active_minutes: int | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    message_limit: int = Query(0, ge=0, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """List sessions with optional filters and last N messages per session."""
    manager = SessionManager(db)
    sessions = manager.list_sessions(
        channel=channel,
        active_minutes=active_minutes,
        limit=limit,
        message_limit=message_limit if message_limit > 0 else 0,
    )
    items = []
    for s in sessions:
        row = SessionRead.model_validate(s)
        payload = row.model_dump()
        if getattr(s, "messages", None):
            payload["messages"] = [MessageRead.model_validate(m) for m in s.messages]
            payload["message_count"] = len(s.messages)
        else:
            payload["messages"] = None
            payload["message_count"] = None
        items.append(SessionListRow(**payload))
    return {"items": items}


@sessions_router.get("/{session_id}", response_model=SessionRead)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
) -> SessionRead:
    """Get a session by ID."""
    svc = SessionService(db)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


@sessions_router.get("/{session_id}/messages", response_model=dict)
def list_session_messages(
    session_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """List messages for a session."""
    svc = SessionService(db)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from app.services.session_message_service import SessionMessageService

    msg_svc = SessionMessageService(db)
    messages = msg_svc.get_messages(session_id, limit=limit, offset=offset)
    items = [MessageRead.model_validate(m) for m in messages]
    return {"items": items}


@sessions_router.post("/{session_id}/reset", response_model=SessionRead)
def reset_session(
    session_id: UUID,
    db: Session = Depends(get_db),
) -> SessionRead:
    """Reset a session (new session id, same key)."""
    svc = SessionService(db)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    manager = SessionManager(db)
    new_session = manager.reset_session(session.session_key)
    return SessionRead.model_validate(new_session)


@sessions_router.post("/{session_id}/compact", response_model=dict)
def compact_session(
    session_id: UUID,
    keep_last_n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Compact older messages into a summary (stub summarizer)."""
    svc = SessionService(db)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    manager = SessionManager(db)
    manager.compact_session(session_id, keep_last_n=keep_last_n)
    return {"ok": True}
