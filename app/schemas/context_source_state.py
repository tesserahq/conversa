"""Pydantic schemas for context source sync state (read-only view)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ContextSourceStateRead(BaseModel):
    """Response schema for a (source, user) sync state row."""

    user_id: UUID
    user_email: str | None
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_error: str | None
    next_run_at: datetime | None
    etag: str | None
