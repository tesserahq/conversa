"""Context sources API: CRUD for the Source Registry."""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.db import get_db
from app.models.context_source import ContextSource
from app.routers.utils.dependencies import get_context_source_by_id
from app.schemas.context_source import (
    ContextSourceCreate,
    ContextSourceRead,
    ContextSourceUpdate,
)
from app.services.context_source_service import ContextSourceService
from tessera_sdk.utils.auth import get_current_user

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
