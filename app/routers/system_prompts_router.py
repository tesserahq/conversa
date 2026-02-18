"""System prompts API: CRUD and version management with RBAC."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.db import get_db
from app.models.system_prompt import SystemPromptVersion
from app.schemas.system_prompt import (
    SystemPromptCreate,
    SystemPromptCurrentRead,
    SystemPromptRead,
    SystemPromptUpdate,
    SystemPromptVersionCreate,
    SystemPromptVersionRead,
)
from app.services.system_prompt_service import SystemPromptService
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="/prompts",
    tags=["system-prompts"],
    responses={404: {"description": "Not found"}},
)


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_PROMPTS = "system.prompts"
rbac_prompts = build_rbac_dependencies(
    resource=RESOURCE_PROMPTS,
    domain_resolver=infer_domain,
)


@router.get(
    "",
    response_model=dict,
)
def list_system_prompts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _authorized: bool = Depends(rbac_prompts["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """List all system prompts."""
    svc = SystemPromptService(db)
    prompts = svc.get_system_prompts(skip=skip, limit=limit)
    items = [SystemPromptRead.model_validate(p) for p in prompts]
    return {"items": items}


@router.post(
    "",
    response_model=SystemPromptRead,
    status_code=201,
)
def create_system_prompt(
    data: SystemPromptCreate,
    _authorized: bool = Depends(rbac_prompts["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemPromptRead:
    """Create a new system prompt with optional initial content."""
    svc = SystemPromptService(db)
    try:
        prompt = svc.create_prompt(
            name=data.name,
            initial_content=data.content,
            note=data.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return SystemPromptRead.model_validate(prompt)


@router.get(
    "/{name}",
    response_model=SystemPromptRead,
)
def get_system_prompt(
    name: str,
    _authorized: bool = Depends(rbac_prompts["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemPromptRead:
    """Get a system prompt by name."""
    svc = SystemPromptService(db)
    prompt = svc.get_system_prompt_by_name(name)
    if prompt is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return SystemPromptRead.model_validate(prompt)


@router.patch(
    "/{name}",
    response_model=SystemPromptRead,
)
def update_system_prompt(
    name: str,
    data: SystemPromptUpdate,
    _authorized: bool = Depends(rbac_prompts["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemPromptRead:
    """Update a system prompt (e.g. rename)."""
    svc = SystemPromptService(db)
    try:
        prompt = svc.update_prompt_name(name, new_name=data.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if prompt is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return SystemPromptRead.model_validate(prompt)


@router.delete(
    "/{name}",
    status_code=204,
)
def delete_system_prompt(
    name: str,
    _authorized: bool = Depends(rbac_prompts["delete"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a system prompt and all its versions."""
    svc = SystemPromptService(db)
    if not svc.delete_prompt(name):
        raise HTTPException(status_code=404, detail="System prompt not found")


@router.get(
    "/{name}/current",
    response_model=SystemPromptCurrentRead,
)
def get_system_prompt_current(
    name: str,
    _authorized: bool = Depends(rbac_prompts["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemPromptCurrentRead:
    """Return the current system prompt content and version info."""
    svc = SystemPromptService(db)
    prompt = svc.get_system_prompt_by_name(name)
    if prompt is None or prompt.current_version_id is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    version = (
        db.query(SystemPromptVersion)
        .filter(SystemPromptVersion.id == prompt.current_version_id)
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="System prompt version not found")
    return SystemPromptCurrentRead(
        content=str(version.content),
        version_id=version.id,
        version_number=int(version.version_number),
        updated_at=prompt.updated_at,
    )


@router.get(
    "/{name}/versions",
    response_model=dict,
)
def list_system_prompt_versions(
    name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _authorized: bool = Depends(rbac_prompts["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """List version history for the given system prompt, newest first."""
    svc = SystemPromptService(db)
    versions = svc.get_versions(name, skip=skip, limit=limit)
    items = [SystemPromptVersionRead.model_validate(v) for v in versions]
    return {"items": items}


@router.post(
    "/{name}/versions",
    response_model=SystemPromptVersionRead,
    status_code=201,
)
def create_system_prompt_version(
    name: str,
    data: SystemPromptVersionCreate,
    _authorized: bool = Depends(rbac_prompts["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemPromptVersionRead:
    """Create a new version and set it as the current system prompt."""
    svc = SystemPromptService(db)
    version = svc.create_version(name, content=data.content, note=data.note)
    if version is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return SystemPromptVersionRead.model_validate(version)
