from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.context_source import ContextSource
from app.services.context_source_service import ContextSourceService


def get_context_source_by_id(
    id: UUID,
    db: Session = Depends(get_db),
) -> ContextSource:
    """FastAPI dependency to get a context source by ID."""
    source = ContextSourceService(db).get_context_source(id)
    if source is None:
        raise HTTPException(status_code=404, detail="Context source not found")
    return source
