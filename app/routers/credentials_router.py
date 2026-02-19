"""Credentials API: CRUD for context source auth credentials."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.db import get_db
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialUpdate
from app.services.credential_service import CredentialService
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="",
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


@router.get("", response_model=Page[CredentialRead])
def list_credentials(
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[CredentialRead]:
    """List all credentials with pagination."""
    svc = CredentialService(db)
    query = svc.get_credentials_query()
    return paginate(query, params=params)


@router.post("", response_model=CredentialRead, status_code=201)
def create_credential(
    data: CredentialCreate,
    _authorized: bool = Depends(rbac["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialRead:
    """Create a new credential."""
    svc = CredentialService(db)
    credential = svc.create_credential(
        data,
        created_by_id=getattr(_current_user, "id", None),
    )
    return credential


@router.get("/{credential_id}", response_model=CredentialRead)
def get_credential(
    credential_id: UUID,
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialRead:
    """Get a credential by ID."""
    svc = CredentialService(db)
    credential = svc.get_credential(credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return credential


@router.patch("/{credential_id}", response_model=CredentialRead)
def update_credential(
    credential_id: UUID,
    data: CredentialUpdate,
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialRead:
    """Update a credential."""
    svc = CredentialService(db)
    credential = svc.update_credential(credential_id, data)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return credential


@router.delete("/{credential_id}", status_code=204)
def delete_credential(
    credential_id: UUID,
    _authorized: bool = Depends(rbac["delete"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft delete a credential."""
    svc = CredentialService(db)
    if not svc.delete_credential(credential_id):
        raise HTTPException(status_code=404, detail="Credential not found")
