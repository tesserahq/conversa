"""Context sources API: CRUD for the Source Registry."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.commands.sync_context_for_user_command import SyncContextForUserCommand
from app.db import get_db
from app.models.context_source import ContextSource
from app.models.user import User
from app.routers.utils.dependencies import get_context_source_by_id, get_user_by_id
from app.schemas.context_source import (
    ContextSourceCreate,
    ContextSourceRead,
    ContextSourceUpdate,
)
from app.services.context_source_service import ContextSourceService
from tessera_sdk.utils.auth import get_current_user
from app.infra.logging_config import get_logger

logger = get_logger("context_sources")

router = APIRouter(
    prefix="",
    tags=["context-sources"],
    responses={404: {"description": "Not found"}},
)


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_SOURCES = "context_source"
rbac = build_rbac_dependencies(
    resource=RESOURCE_SOURCES,
    domain_resolver=infer_domain,
)


class ContextSyncResponse(BaseModel):
    """Response for manual context sync."""

    user_id: str
    status: str = "synced"


@router.post("/sync/{user_id}", response_model=ContextSyncResponse)
def trigger_context_sync(
    user_id: UUID,
    _user: User = Depends(get_user_by_id),
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContextSyncResponse:
    """Manually trigger context sync for a user. Fetches from all enabled sources, merges, and stores snapshot."""
    command = SyncContextForUserCommand(db)
    result = command.execute(user_id)
    logger.info("Context sync result: %s", result)
    if result is None:
        raise HTTPException(
            status_code=500,
            detail="Context sync failed",
        )
    return ContextSyncResponse(user_id=str(result), status="synced")


@router.get("", response_model=Page[ContextSourceRead])
def list_context_sources(
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[ContextSourceRead]:
    """List all context sources with pagination."""
    svc = ContextSourceService(db)
    query = svc.get_context_sources_query()
    return paginate(query, params=params)


@router.post("", response_model=ContextSourceRead, status_code=201)
def create_context_source(
    data: ContextSourceCreate,
    _authorized: bool = Depends(rbac["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContextSourceRead:
    """Create a new context source."""
    svc = ContextSourceService(db)
    source = svc.create_context_source(data)
    return source


@router.get("/{id}", response_model=ContextSourceRead)
def get_context_source(
    source: ContextSource = Depends(get_context_source_by_id),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
) -> ContextSourceRead:
    """Get a context source by ID."""
    return source


@router.patch("/{id}", response_model=ContextSourceRead)
def update_context_source(
    data: ContextSourceUpdate,
    source: ContextSource = Depends(get_context_source_by_id),
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContextSourceRead:
    """Update a context source."""
    return ContextSourceService(db).update_context_source(source.id, data)


@router.delete("/{id}", status_code=204)
def delete_context_source(
    source: ContextSource = Depends(get_context_source_by_id),
    _authorized: bool = Depends(rbac["delete"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft delete a context source."""
    ContextSourceService(db).delete_context_source(source.id)
