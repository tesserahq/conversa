"""Service for context source state (per-source, per-user sync state)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.context_source import ContextSource
from app.models.context_source import ContextSourceState
from app.models.user import User
from app.services.context_source_service import ContextSourceService
from app.services.soft_delete_service import SoftDeleteService
from app.services.user_service import UserService


class ContextSourceStateService:
    """Manages per-source, per-user sync state for context pack sync."""

    def __init__(
        self,
        db: Session,
        context_source_service: Optional[ContextSourceService] = None,
        user_service: Optional[UserService] = None,
    ) -> None:
        self._db = db
        self._source_svc = context_source_service or ContextSourceService(db)
        self._user_svc = user_service or UserService(db)

    def get_or_create_state(
        self,
        source_id: UUID,
        user_id: UUID,
    ) -> ContextSourceState:
        """Get or create state for (source, user)."""
        state = (
            self._db.query(ContextSourceState)
            .filter(
                ContextSourceState.source_id == source_id,
                ContextSourceState.user_id == user_id,
            )
            .first()
        )
        if state is not None:
            return state
        state = ContextSourceState(
            source_id=source_id,
            user_id=user_id,
        )
        self._db.add(state)
        self._db.commit()
        self._db.refresh(state)
        return state

    def update_state(
        self,
        state: ContextSourceState,
        *,
        last_success_at: Optional[datetime] = None,
        last_attempt_at: Optional[datetime] = None,
        last_error: Optional[str] = None,
        etag: Optional[str] = None,
        since_cursor: Optional[str] = None,
        next_run_at: Optional[datetime] = None,
    ) -> None:
        """Update state fields (only non-None values)."""
        if last_success_at is not None:
            state.last_success_at = last_success_at
        if last_attempt_at is not None:
            state.last_attempt_at = last_attempt_at
        if last_error is not None:
            state.last_error = last_error
        if etag is not None:
            state.etag = etag
        if since_cursor is not None:
            state.since_cursor = since_cursor
        if next_run_at is not None:
            state.next_run_at = next_run_at
        self._db.commit()
        self._db.refresh(state)

    def get_due_user_source_pairs(
        self,
        limit: int = 500,
    ) -> List[Tuple[ContextSource, User]]:
        """
        Enumerate (source, user) pairs due for sync.

        Returns enabled sources x users (from users table, non-deleted),
        where next_run_at <= now or no state exists.
        """
        now = datetime.now(timezone.utc)
        sources = [
            s
            for s in self._source_svc.get_context_sources(skip=0, limit=200)
            if s.enabled and s.deleted_at is None
        ]
        users = self._user_svc.get_users(skip=0, limit=1000)
        users_by_id = {u.id: u for u in users}

        result: List[Tuple[ContextSource, User]] = []
        seen: set[Tuple[UUID, UUID]] = set()

        for source in sources:
            for user in users:
                if (source.id, user.id) in seen:
                    continue
                state = (
                    self._db.query(ContextSourceState)
                    .filter(
                        ContextSourceState.source_id == source.id,
                        ContextSourceState.user_id == user.id,
                    )
                    .first()
                )
                if state is None:
                    due = True
                else:
                    next_run = state.next_run_at
                    if next_run is not None and next_run.tzinfo is None:
                        next_run = next_run.replace(tzinfo=timezone.utc)
                    due = next_run is not None and next_run <= now
                if due:
                    result.append((source, user))
                    seen.add((source.id, user.id))
                    if len(result) >= limit:
                        return result
        return result
