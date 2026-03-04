"""
Utilities for building context_source-related CloudEvents payloads.
"""

from __future__ import annotations

from uuid import UUID

from app.models.context_source import ContextSource as ContextSourceModel
from app.schemas.context_source import ContextSourceRead as ContextSourceSchema
from tessera_sdk.events.event import Event, event_source, event_type  # type: ignore[import-untyped]

# Context source events
CONTEXT_SOURCE_CREATED = "context_source.created"
CONTEXT_SOURCE_UPDATED = "context_source.updated"
CONTEXT_SOURCE_DELETED = "context_source.deleted"


def build_context_source_created_event(
    source: ContextSourceModel,
    created_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for context source creation."""
    source_schema = ContextSourceSchema.model_validate(source)
    event_data: dict[str, object] = {
        "context_source": source_schema.model_dump(mode="json"),
    }
    if created_by_id is not None:
        event_data["created_by_id"] = str(created_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(CONTEXT_SOURCE_CREATED),
        event_data=event_data,
        subject=f"/context-sources/{source.id}",
        user_id=str(created_by_id) if created_by_id else "",
        labels={"context_source_id": str(source.id)},
        tags=[f"context_source_id:{source.id}"],
    )


def build_context_source_updated_event(
    source: ContextSourceModel,
    updated_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for context source update."""
    source_schema = ContextSourceSchema.model_validate(source)
    event_data: dict[str, object] = {
        "context_source": source_schema.model_dump(mode="json"),
    }
    if updated_by_id is not None:
        event_data["updated_by_id"] = str(updated_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(CONTEXT_SOURCE_UPDATED),
        event_data=event_data,
        subject=f"/context-sources/{source.id}",
        user_id=str(updated_by_id) if updated_by_id else "",
        labels={"context_source_id": str(source.id)},
        tags=[f"context_source_id:{source.id}"],
    )


def build_context_source_deleted_event(
    source: ContextSourceModel,
    deleted_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for context source deletion."""
    source_schema = ContextSourceSchema.model_validate(source)
    event_data: dict[str, object] = {
        "context_source": source_schema.model_dump(mode="json"),
    }
    if deleted_by_id is not None:
        event_data["deleted_by_id"] = str(deleted_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(CONTEXT_SOURCE_DELETED),
        event_data=event_data,
        subject=f"/context-sources/{source.id}",
        user_id=str(deleted_by_id) if deleted_by_id else "",
        labels={"context_source_id": str(source.id)},
        tags=[f"context_source_id:{source.id}"],
    )
