"""System prompts API: CRUD and version management with RBAC."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.db import get_db
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


RESOURCE_PROMPTS = "system_prompt"
rbac_prompts = build_rbac_dependencies(
    resource=RESOURCE_PROMPTS,
    domain_resolver=infer_domain,
)


@router.get(
    "",
    response_model=Page[SystemPromptRead],
)
def list_system_prompts(
    params: Params = Depends(),
    _authorized: bool = Depends(rbac_prompts["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[SystemPromptRead]:
    """List all system prompts with pagination."""
    svc = SystemPromptService(db)
    query = svc.get_system_prompts_query()
    return paginate(query, params=params)


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
    prompt = svc.create_prompt(
        name=data.name,
        initial_content=data.content,
        note=data.note,
    )
    return prompt


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
    return prompt


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
    prompt = svc.update_prompt_name(name, new_name=data.name)
    if prompt is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt


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
    result = svc.get_current_version_display(name)
    if result is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    version, prompt = result
    return SystemPromptCurrentRead(
        content=str(version.content),
        version_id=version.id,
        version_number=int(version.version_number),
        updated_at=prompt.updated_at,
    )


@router.get(
    "/{name}/versions",
    response_model=Page[SystemPromptVersionRead],
)
def list_system_prompt_versions(
    name: str,
    params: Params = Depends(),
    _authorized: bool = Depends(rbac_prompts["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[SystemPromptVersionRead]:
    """List version history for the given system prompt, newest first."""
    svc = SystemPromptService(db)
    query = svc.get_versions_query(name)
    return paginate(query, params=params)


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
    return version
