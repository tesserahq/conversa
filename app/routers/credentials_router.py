"""Credentials API: CRUD for context source auth credentials."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_pagination import Page, Params, create_page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.commands.credentials import CreateCredentialCommand
from app.core.credentials import credential_registry
from app.db import get_db
from app.schemas.credential import (
    CredentialCreate,
    CredentialFieldsReveal,
    CredentialRead,
    CredentialTypeInfo,
    CredentialUpdate,
)
from app.repositories.credential_repository import CredentialRepository
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="/credentials",
    tags=["credentials"],
    responses={404: {"description": "Not found"}},
)


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_CREDENTIALS = "credential"
rbac = build_rbac_dependencies(
    resource=RESOURCE_CREDENTIALS,
    domain_resolver=infer_domain,
)


@router.get("/types", response_model=list[CredentialTypeInfo])
def list_credential_types(
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
) -> list[CredentialTypeInfo]:
    """List available credential types and their attributes for UI rendering."""
    return list(credential_registry.values())


@router.get("", response_model=Page[CredentialRead])
def list_credentials(
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[CredentialRead]:
    """List all credentials with pagination."""
    svc = CredentialRepository(db)
    query = svc.get_credentials_query()
    page = paginate(query, params=params)
    items = [svc.to_credential_read(c) for c in page.items]
    return create_page(items, total=page.total, params=params)


@router.post("", response_model=CredentialRead, status_code=201)
def create_credential(
    data: CredentialCreate,
    _authorized: bool = Depends(rbac["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialRead:
    """Create a new credential."""
    command = CreateCredentialCommand(db)
    credential = command.execute(
        data,
        created_by_id=getattr(_current_user, "id", None),
    )
    svc = CredentialRepository(db)
    return svc.to_credential_read(credential)


@router.get("/{credential_id}", response_model=CredentialRead)
def get_credential(
    credential_id: UUID,
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialRead:
    """Get a credential by ID."""
    svc = CredentialRepository(db)
    credential = svc.get_credential(credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return svc.to_credential_read(credential)


@router.post(
    "/{credential_id}/reveal-fields",
    response_model=CredentialFieldsReveal,
    status_code=200,
)
def reveal_credential_fields(
    credential_id: UUID,
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialFieldsReveal:
    """Return decrypted credential field values. Use only when you need to verify or edit stored data."""
    svc = CredentialRepository(db)
    credential = svc.get_credential(credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    fields = svc.get_credential_fields(credential_id)
    if fields is None:
        raise HTTPException(
            status_code=500,
            detail="Could not decrypt credential fields",
        )
    return CredentialFieldsReveal(fields=fields)


@router.patch("/{credential_id}", response_model=CredentialRead)
def update_credential(
    credential_id: UUID,
    data: CredentialUpdate,
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialRead:
    """Update a credential."""
    svc = CredentialRepository(db)
    credential = svc.update_credential(credential_id, data)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return svc.to_credential_read(credential)


@router.delete("/{credential_id}", status_code=204)
def delete_credential(
    credential_id: UUID,
    _authorized: bool = Depends(rbac["delete"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft delete a credential."""
    svc = CredentialRepository(db)
    if not svc.delete_credential(credential_id):
        raise HTTPException(status_code=404, detail="Credential not found")
