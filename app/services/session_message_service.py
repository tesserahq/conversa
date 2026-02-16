"""SessionMessage CRUD and get_messages."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session as DBSession

from app.models.session_message import SessionMessage
from app.schemas.session import MessageCreate
from uuid import UUID


class SessionMessageService:
    def __init__(self, db: DBSession) -> None:
        self.db = db

    def create_message(self, session_id: UUID, data: MessageCreate) -> SessionMessage:
        dump = data.model_dump()
        extra = dump.pop("metadata", None)
        msg = SessionMessage(
            session_id=session_id,
            extra=extra,
            **dump,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
        include_tools: bool = True,
    ) -> List[SessionMessage]:
        query = (
            self.db.query(SessionMessage)
            .filter(SessionMessage.session_id == session_id)
            .order_by(SessionMessage.created_at)
            .offset(offset)
            .limit(limit)
        )
        # include_tools: if False, filter out tool-related messages (e.g. by metadata)
        # For now we don't have tool messages; leave as-is.
        return query.all()

    def delete_messages_for_session(self, session_id: UUID) -> int:
        deleted = (
            self.db.query(SessionMessage)
            .filter(SessionMessage.session_id == session_id)
            .delete()
        )
        self.db.commit()
        return deleted

    def get_message_count(self, session_id: UUID) -> int:
        return (
            self.db.query(SessionMessage)
            .filter(SessionMessage.session_id == session_id)
            .count()
        )
