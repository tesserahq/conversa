"""Sessions API: list, get, messages, reset, compact."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi_pagination import Page, Params, create_page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.db import get_db
from app.schemas.session import MessageRead, SessionListRow, SessionRead
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from tessera_sdk.utils.auth import get_current_user

sessions_router = APIRouter(prefix="/sessions", tags=["Session"])


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_SESSIONS = "session"
rbac = build_rbac_dependencies(
    resource=RESOURCE_SESSIONS,
    domain_resolver=infer_domain,
)


def _session_to_list_row(s) -> SessionListRow:
    """Convert session to SessionListRow."""
    row = SessionRead.model_validate(s)
    payload = row.model_dump()
    if getattr(s, "messages", None):
        payload["messages"] = [MessageRead.model_validate(m) for m in s.messages]
        payload["message_count"] = len(s.messages)
    else:
        payload["messages"] = None
        payload["message_count"] = None
    return SessionListRow(**payload)


@sessions_router.get("", response_model=Page[SessionListRow])
def list_sessions(
    params: Params = Depends(),
    channel: str | None = Query(None),
    active_minutes: int | None = Query(None),
    message_limit: int = Query(0, ge=0, le=50),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[SessionListRow]:
    """List sessions with optional filters and last N messages per session."""
    manager = SessionManager(db)
    query = manager.get_sessions_query(
        channel=channel,
        active_minutes=active_minutes,
    )
    page = paginate(query, params=params)
    if message_limit > 0:
        manager.attach_recent_messages(page.items, message_limit)
    rows = [_session_to_list_row(s) for s in page.items]
    return create_page(rows, total=page.total, params=page.params)


@sessions_router.get("/{session_id}", response_model=SessionRead)
def get_session(
    session_id: UUID,
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionRead:
    """Get a session by ID."""
    svc = SessionService(db)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


@sessions_router.get("/{session_id}/messages", response_model=Page[MessageRead])
def list_session_messages(
    session_id: UUID,
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[MessageRead]:
    """List messages for a session with pagination."""
    svc = SessionService(db)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from app.services.session_message_service import SessionMessageService

    msg_svc = SessionMessageService(db)
    query = msg_svc.get_messages_query(session_id)
    return paginate(query, params=params)


@sessions_router.post("/{session_id}/reset", response_model=SessionRead)
def reset_session(
    session_id: UUID,
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
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
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
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
