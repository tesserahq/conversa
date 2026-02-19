"""Session CRUD and get_or_create by key."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Query, Session as DBSession

from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters
from uuid import UUID


class SessionService(SoftDeleteService[Session]):
    def __init__(self, db: DBSession) -> None:
        super().__init__(db, Session)

    def get_session(self, session_id: UUID) -> Optional[Session]:
        return self.db.query(Session).filter(Session.id == session_id).first()

    def get_sessions(self, skip: int = 0, limit: int = 100) -> List[Session]:
        return self.db.query(Session).offset(skip).limit(limit).all()

    def get_session_by_key(self, session_key: str) -> Optional[Session]:
        return self.db.query(Session).filter(Session.session_key == session_key).first()

    def get_or_create_by_key(
        self,
        session_key: str,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Session, bool]:
        """
        Get existing session by key or create one. Returns (session, created).
        When creating, defaults must include at least channel and chat_id.
        """
        session = self.get_session_by_key(session_key)
        if session is not None:
            return session, False
        defaults = dict(defaults or {})
        defaults.setdefault("session_key", session_key)
        defaults.setdefault("last_message_at", datetime.now(timezone.utc))
        if "channel" not in defaults or "chat_id" not in defaults:
            raise ValueError(
                "defaults must include 'channel' and 'chat_id' when creating a session"
            )
        data = SessionCreate(**defaults)
        session = self.create_session(data)
        return session, True

    def create_session(self, data: SessionCreate) -> Session:
        session = Session(**data.model_dump())
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_session(
        self, session_id: UUID, data: SessionUpdate
    ) -> Optional[Session]:
        session = self.db.query(Session).filter(Session.id == session_id).first()
        if session is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(session, key, value)
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: UUID) -> bool:
        return self.delete_record(session_id)

    def search(self, filters: Dict[str, Any]) -> List[Session]:
        query = self.db.query(Session)
        query = apply_filters(query, Session, filters)
        return query.all()

    def search_query(self, filters: Dict[str, Any]) -> Query[Session]:
        """Get a query for sessions with filters (for pagination)."""
        query = self.db.query(Session)
        return apply_filters(query, Session, filters)
