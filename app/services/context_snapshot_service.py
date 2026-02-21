"""Service for context snapshot CRUD and chat-time read."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.context_snapshot import ContextSnapshot


class ContextSnapshotService:
    """Manages context snapshots for chat-time reads and sync worker writes."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_latest_snapshot(self, user_id: UUID) -> Optional[ContextSnapshot]:
        """Fetch the most recent snapshot for a user (chat-time read path)."""
        return (
            self._db.query(ContextSnapshot)
            .filter(ContextSnapshot.user_id == user_id)
            .order_by(desc(ContextSnapshot.generated_at))
            .first()
        )

    def create_snapshot(
        self,
        user_id: UUID,
        schema_version: str,
        generated_at: datetime,
        payload: dict,
        payload_hash: Optional[str] = None,
    ) -> ContextSnapshot:
        """Create a new context snapshot (sync worker write path)."""
        snapshot = ContextSnapshot(
            user_id=user_id,
            schema_version=schema_version,
            generated_at=generated_at,
            payload=payload,
            payload_hash=payload_hash,
        )
        self._db.add(snapshot)
        self._db.commit()
        self._db.refresh(snapshot)
        return snapshot
