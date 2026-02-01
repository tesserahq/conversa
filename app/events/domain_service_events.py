"""
Utilities for building domain service-related CloudEvents payloads.
"""

from __future__ import annotations

from app.models.domain_service import DomainService as DomainServiceModel
from app.models.user import User as UserModel
from app.schemas.domain_service import DomainService
from app.schemas.user import User

from tessera_sdk.events.event import Event, event_type, event_source

# Domain service event types
DOMAIN_SERVICE_CREATED = "indexing.domain_service.created"
DOMAIN_SERVICE_UPDATED = "indexing.domain_service.updated"
DOMAIN_SERVICE_DELETED = "indexing.domain_service.deleted"


def build_domain_service_created_event(
    domain_service: DomainServiceModel,
    created_by: UserModel,
) -> Event:
    """
    Create a CloudEvent for domain service created.

    Args:
        domain_service: The domain service model instance
        created_by: User who created the service

    Returns:
        Event: CloudEvent for domain service created
    """
    domain_service_schema = DomainService.model_validate(domain_service)
    user_schema = User.model_validate(created_by)

    event_data = {
        "domain_service": domain_service_schema.model_dump(mode="json"),
        "user": user_schema.model_dump(mode="json"),
    }

    return Event(
        source=event_source(f"/domain-services/{domain_service.id}"),
        event_type=event_type(DOMAIN_SERVICE_CREATED),
        event_data=event_data,
        subject=f"/domain-services/{domain_service.id}",
        user_id=str(created_by.id),
        labels={
            "service_id": str(domain_service.id),
            "service_name": domain_service.name,
            "action": "created",
        },
        tags=[
            f"service_id:{str(domain_service.id)}",
            f"service_name:{domain_service.name}",
            "action:created",
        ],
    )


def build_domain_service_updated_event(
    domain_service: DomainServiceModel,
    updated_by: UserModel,
) -> Event:
    """
    Create a CloudEvent for domain service updated.

    Args:
        domain_service: The domain service model instance
        updated_by: User who updated the service

    Returns:
        Event: CloudEvent for domain service updated
    """
    domain_service_schema = DomainService.model_validate(domain_service)
    user_schema = User.model_validate(updated_by)

    event_data = {
        "domain_service": domain_service_schema.model_dump(mode="json"),
        "user": user_schema.model_dump(mode="json"),
    }

    return Event(
        source=event_source(f"/domain-services/{domain_service.id}"),
        event_type=event_type(DOMAIN_SERVICE_UPDATED),
        event_data=event_data,
        subject=f"/domain-services/{domain_service.id}",
        user_id=str(updated_by.id),
        labels={
            "service_id": str(domain_service.id),
            "service_name": domain_service.name,
            "action": "updated",
        },
        tags=[
            f"service_id:{str(domain_service.id)}",
            f"service_name:{domain_service.name}",
            "action:updated",
        ],
    )


def build_domain_service_deleted_event(
    domain_service: DomainServiceModel,
    deleted_by: UserModel,
) -> Event:
    """
    Create a CloudEvent for domain service deleted.

    Args:
        domain_service: The domain service model instance
        deleted_by: User who deleted the service

    Returns:
        Event: CloudEvent for domain service deleted
    """
    domain_service_schema = DomainService.model_validate(domain_service)
    user_schema = User.model_validate(deleted_by)

    event_data = {
        "domain_service": domain_service_schema.model_dump(mode="json"),
        "user": user_schema.model_dump(mode="json"),
    }

    return Event(
        source=event_source(f"/domain-services/{domain_service.id}"),
        event_type=event_type(DOMAIN_SERVICE_DELETED),
        event_data=event_data,
        subject=f"/domain-services/{domain_service.id}",
        user_id=str(deleted_by.id),
        labels={
            "service_id": str(domain_service.id),
            "service_name": domain_service.name,
            "action": "deleted",
        },
        tags=[
            f"service_id:{str(domain_service.id)}",
            f"service_name:{domain_service.name}",
            "action:deleted",
        ],
    )
