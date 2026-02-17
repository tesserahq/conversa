from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.schemas.system import (
    GeneralGroup,
    SystemSettingsGrouped,
    AppGroup,
    DatabaseGroup,
    TelemetryGroup,
    RedisGroup,
    ExternalServicesGroup,
)
from app.schemas.system_prompt import (
    SystemPromptCurrentRead,
    SystemPromptVersionCreate,
    SystemPromptVersionRead,
)
from tessera_sdk.utils.auth import get_current_user
from app.config import get_settings
from app.auth.rbac import build_rbac_dependencies
from app.db import get_db
from app.models.system_prompt import SystemPromptVersion
from app.services.system_prompt_service import SystemPromptService

router = APIRouter(
    prefix="/system",
    tags=["system"],
    responses={404: {"description": "Not found"}},
)


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE = "system.settings"
rbac = build_rbac_dependencies(
    resource=RESOURCE,
    domain_resolver=infer_domain,
)


@router.get("/settings", response_model=SystemSettingsGrouped)
def get_system_settings(
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
) -> SystemSettingsGrouped:
    """Return grouped, non-sensitive system configuration settings for troubleshooting."""
    s = get_settings()

    app_group = AppGroup(
        name=s.app_name,
        environment=s.environment,
        log_level=s.log_level,
        disable_auth=s.disable_auth,
        port=s.port,
    )

    # Extract safe database info only (no credentials)
    database_host = None
    database_driver = None
    try:
        url_obj = s.database_url_obj
        database_host = url_obj.host
        database_driver = url_obj.get_backend_name()
    except Exception:
        pass

    database_group = DatabaseGroup(
        database_host=database_host,
        database_driver=database_driver,
        pool_size=s.database_pool_size,
        max_overflow=s.database_max_overflow,
    )

    general_group = GeneralGroup(
        is_production=s.is_production,
    )

    telemetry_group = TelemetryGroup(
        otel_enabled=s.otel_enabled,
        otel_exporter_otlp_endpoint=s.otel_exporter_otlp_endpoint,
        otel_service_name=s.otel_service_name,
    )

    redis_group = RedisGroup(
        host=s.redis_host,
        port=s.redis_port,
        namespace=s.redis_namespace,
    )

    services_group = ExternalServicesGroup(
        vaulta_api_url=s.vaulta_api_url,
        identies_base_url=s.identies_base_url,
    )

    grouped = SystemSettingsGrouped(
        app=app_group,
        database=database_group,
        general=general_group,
        telemetry=telemetry_group,
        redis=redis_group,
        services=services_group,
    )

    return grouped


# --- System prompt (markdown, versioned) ---


@router.get(
    "/prompts/{name}/current",
    response_model=SystemPromptCurrentRead,
)
def get_system_prompt_current(
    name: str,
    _authorized: bool = Depends(rbac["read"]),
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
        content=version.content,
        version_id=version.id,
        version_number=version.version_number,
        updated_at=prompt.updated_at,
    )


@router.get(
    "/prompts/{name}/versions",
    response_model=dict,
)
def list_system_prompt_versions(
    name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """List version history for the given system prompt, newest first."""
    svc = SystemPromptService(db)
    versions = svc.get_versions(name, skip=skip, limit=limit)
    items = [SystemPromptVersionRead.model_validate(v) for v in versions]
    return {"items": items}


@router.post(
    "/prompts/{name}/versions",
    response_model=SystemPromptVersionRead,
    status_code=201,
)
def create_system_prompt_version(
    name: str,
    data: SystemPromptVersionCreate,
    _authorized: bool = Depends(rbac["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemPromptVersionRead:
    """Create a new version and set it as the current system prompt."""
    svc = SystemPromptService(db)
    version = svc.create_version(name, content=data.content, note=data.note)
    if version is None:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return SystemPromptVersionRead.model_validate(version)
