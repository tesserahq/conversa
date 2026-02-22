from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.context_source import ContextSource
from app.models.user import User
from app.services.context_source_service import ContextSourceService
from app.services.user_service import UserService


def get_user_by_id(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency to get a user by ID."""
    user = UserService(db).get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_context_source_by_id(
    id: UUID,
    db: Session = Depends(get_db),
) -> ContextSource:
    """FastAPI dependency to get a context source by ID."""
    source = ContextSourceService(db).get_context_source(id)
    if source is None:
        raise HTTPException(status_code=404, detail="Context source not found")
    return source
