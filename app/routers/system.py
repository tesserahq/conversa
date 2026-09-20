from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from tessera_sdk.config import get_settings as get_sdk_settings
from tessera_sdk.server.dependencies.auth import get_current_user

from app.auth.rbac import build_rbac_dependencies
from app.config import get_settings
from app.schemas.system import (
    AppGroup,
    DatabaseGroup,
    ExternalServicesGroup,
    GeneralGroup,
    RedisGroup,
    SystemSettingsGrouped,
    TelemetryGroup,
)

router = APIRouter(
    prefix="/system",
    tags=["system"],
    responses={404: {"description": "Not found"}},
)


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_SETTINGS = "system.settings"
rbac = build_rbac_dependencies(
    resource=RESOURCE_SETTINGS,
    domain_resolver=infer_domain,
)


def _get_redis_group() -> RedisGroup:
    settings = get_sdk_settings()
    connection_url = urlsplit(settings.redis_connection_url)

    return RedisGroup(
        host=connection_url.hostname or settings.redis_host,
        port=connection_url.port or settings.redis_port,
        namespace=settings.redis_namespace,
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

    redis_group = _get_redis_group()

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
