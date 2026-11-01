"""Service for context source state (per-source, per-user sync state)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, nulls_last, or_, select, true
from sqlalchemy.orm import Query, Session, joinedload

from app.models.context_source import ContextSource
from app.models.context_source import ContextSourceState
from app.models.user import User


class ContextSourceStateRepository:
    """Manages per-source, per-user sync state for context pack sync."""

    def __init__(self, db: Session) -> None:
        self._db = db

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
        self._db.flush()
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
        self._db.flush()
        self._db.refresh(state)

    def get_states_query(
        self,
        source_id: UUID,
        search: Optional[str] = None,
    ) -> Query[ContextSourceState]:
        """
        Get a query of sync state rows for a source, joined with User for
        email (for pagination). Optionally filtered by a case-insensitive
        substring match on the user's email.
        """
        query = (
            self._db.query(ContextSourceState)
            .join(User, ContextSourceState.user_id == User.id)
            .options(joinedload(ContextSourceState.user))
            .filter(ContextSourceState.source_id == source_id)
        )
        if search:
            query = query.filter(User.email.ilike(f"%{search}%"))
        return query.order_by(nulls_last(ContextSourceState.last_attempt_at.desc()))

    def get_due_user_source_pairs(
        self,
        limit: int = 500,
    ) -> List[Tuple[ContextSource, User]]:
        """
        Enumerate (source, user) pairs due for sync.

        Returns enabled sources x users (from users table, non-deleted),
        where next_run_at <= now or no state exists.
        """
        # Timestamps are stored as naive UTC, so compare against naive UTC.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state_of_pair = and_(
            ContextSourceState.source_id == ContextSource.id,
            ContextSourceState.user_id == User.id,
        )
        statement = (
            select(ContextSource, User)
            .join(User, true())
            .outerjoin(ContextSourceState, state_of_pair)
            .where(
                ContextSource.enabled.is_(True),
                ContextSource.deleted_at.is_(None),
                or_(
                    ContextSourceState.id.is_(None),
                    ContextSourceState.next_run_at <= now,
                ),
            )
            .order_by(ContextSource.source_id, User.id)
            .limit(limit)
        )
        return [(source, user) for source, user in self._db.execute(statement).all()]
