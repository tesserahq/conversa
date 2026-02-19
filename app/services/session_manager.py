"""SessionManager: facade for get_or_create_session, add_turn, get_history_for_llm, reset, list, compact."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Optional

from sqlalchemy.orm import Query, Session as DBSession

from app.channels.envelope import InboundMessage, OutboundMessage
from app.config import get_settings
from app.core.session_key import build_session_key
from app.models.session import Session
from app.schemas.session import MessageCreate
from app.services.session_message_service import SessionMessageService
from app.services.session_service import SessionService
from uuid import UUID


def _is_session_expired(session: Session) -> bool:
    """True if session is expired by daily or idle config. Whichever expires first wins."""
    settings = get_settings()
    mode = (settings.session_expiry_mode or "off").lower()
    if mode == "off":
        return False
    now = datetime.now(timezone.utc)
    last = session.last_message_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    stale_by_daily = False
    stale_by_idle = False
    if mode == "daily":
        at_hour = getattr(settings, "session_expiry_at_hour", 4) or 4
        today_cutoff = now.replace(hour=at_hour, minute=0, second=0, microsecond=0)
        if now.hour < at_hour:
            today_cutoff -= timedelta(days=1)
        stale_by_daily = last < today_cutoff
    if getattr(settings, "session_expiry_idle_minutes", None):
        idle_min = settings.session_expiry_idle_minutes
        idle_cutoff = now - timedelta(minutes=idle_min)
        stale_by_idle = last < idle_cutoff
    return stale_by_daily or stale_by_idle


class SessionManager:
    def __init__(self, db: DBSession) -> None:
        self._db = db
        self._session_svc = SessionService(db)
        self._message_svc = SessionMessageService(db)

    def get_or_create_session(
        self,
        msg: InboundMessage,
        user_id: Optional[UUID] = None,
    ) -> Session:
        key = build_session_key(msg, user_id)
        defaults = {
            "channel": msg.channel,
            "chat_id": msg.chat_id,
            "account_id": msg.account_id,
            "thread_id": msg.thread_id,
            "user_id": user_id,
            "origin": {
                "from": msg.sender_id,
                "to": msg.chat_id,
                "account_id": msg.account_id,
                "thread_id": msg.thread_id,
            },
        }
        session, created = self._session_svc.get_or_create_by_key(key, defaults)
        if not created:
            if _is_session_expired(session):
                self._session_svc.delete_session(session.id)
                session, _ = self._session_svc.get_or_create_by_key(key, defaults)
            else:
                session.last_message_at = datetime.now(timezone.utc)
                if session.origin != defaults.get("origin"):
                    session.origin = defaults.get("origin")
                self._db.commit()
                self._db.refresh(session)
        return session

    def reset_session(self, session_key: str) -> Session:
        existing = self._session_svc.get_session_by_key(session_key)
        if existing is None:
            return self._session_svc.get_or_create_by_key(
                session_key,
                {
                    "channel": "unknown",
                    "chat_id": "unknown",
                },
            )[0]
        defaults = {
            "channel": existing.channel,
            "chat_id": existing.chat_id,
            "account_id": existing.account_id,
            "thread_id": existing.thread_id,
            "user_id": existing.user_id,
            "display_name": existing.display_name,
            "origin": existing.origin,
        }
        self._session_svc.delete_session(existing.id)
        session, _ = self._session_svc.get_or_create_by_key(session_key, defaults)
        return session

    def add_turn(
        self,
        session_id: UUID,
        inbound_msg: InboundMessage,
        outbound_msg: OutboundMessage,
    ) -> None:
        inbound_create = MessageCreate(
            direction="inbound",
            content=inbound_msg.text,
            provider_message_id=inbound_msg.message_id,
            metadata=inbound_msg.raw if inbound_msg.raw else None,
        )
        outbound_create = MessageCreate(
            direction="outbound",
            content=outbound_msg.text,
            reply_to=outbound_msg.reply_to,
        )
        self._message_svc.create_message(session_id, inbound_create)
        self._message_svc.create_message(session_id, outbound_create)
        session = self._session_svc.get_session(session_id)
        if session:
            session.last_message_at = datetime.now(timezone.utc)
            self._db.commit()
            self._db.refresh(session)

    def get_history_for_llm(
        self,
        session_id: UUID,
        limit: int = 50,
        prune_options: Optional[dict[str, Any]] = None,
    ) -> List[dict[str, str]]:
        messages = self._message_svc.get_messages(session_id, limit=limit, offset=0)
        result: List[dict[str, str]] = []
        summary_content: Optional[str] = None
        for m in messages:
            if getattr(m, "extra", None) and (m.extra or {}).get("compact_summary"):
                summary_content = (m.content or "").strip()
                continue
            role = "user" if m.direction == "inbound" else "assistant"
            content = (m.content or "").strip()
            if content:
                result.append({"role": role, "content": content})
        if summary_content:
            result.insert(0, {"role": "system", "content": summary_content})
        return result

    def list_sessions(
        self,
        channel: Optional[str] = None,
        active_minutes: Optional[int] = None,
        limit: int = 100,
        message_limit: int = 0,
    ) -> List[Session]:
        filters: dict[str, Any] = {}
        if channel is not None:
            filters["channel"] = channel
        if active_minutes is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=active_minutes)
            filters["last_message_at"] = {"operator": ">=", "value": cutoff}
        sessions = self._session_svc.search(filters)[:limit]
        if message_limit > 0:
            self.attach_recent_messages(sessions, message_limit)
        return sessions

    def get_sessions_query(
        self,
        channel: Optional[str] = None,
        active_minutes: Optional[int] = None,
    ) -> Query[Session]:
        """Get a query for sessions with filters (for pagination)."""
        filters: dict[str, Any] = {}
        if channel is not None:
            filters["channel"] = channel
        if active_minutes is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=active_minutes)
            filters["last_message_at"] = {"operator": ">=", "value": cutoff}
        return self._session_svc.search_query(filters)

    def attach_recent_messages(
        self, sessions: List[Session], message_limit: int
    ) -> None:
        """Attach the last N messages to each session (modifies in place)."""
        for s in sessions:
            s.messages = self._message_svc.get_messages(
                s.id, limit=message_limit, offset=0
            )

    def compact_session(
        self,
        session_id: UUID,
        keep_last_n: int = 20,
        summarizer: Optional[Callable[[List[dict]], str]] = None,
    ) -> None:
        messages = self._message_svc.get_messages(session_id, limit=1000, offset=0)
        if len(messages) <= keep_last_n:
            return
        to_summarize = messages[:-keep_last_n]
        summary_content = "Previous conversation summary."
        if summarizer is not None:
            history = [
                {
                    "role": "user" if m.direction == "inbound" else "assistant",
                    "content": m.content or "",
                }
                for m in to_summarize
            ]
            summary_content = summarizer(history)
        summary_msg = MessageCreate(
            direction="outbound",
            content=summary_content,
            metadata={"compact_summary": True},
        )
        for m in to_summarize:
            self._db.delete(m)
        self._message_svc.create_message(session_id, summary_msg)
        self._db.commit()
