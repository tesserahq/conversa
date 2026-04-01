"""
Utilities for building system_prompt-related CloudEvents payloads.
"""

from __future__ import annotations

from uuid import UUID

from app.models.system_prompt import SystemPrompt as SystemPromptModel
from app.schemas.system_prompt import SystemPromptRead as SystemPromptSchema
from tessera_sdk.infra.events.event import Event, event_source, event_type  # type: ignore[import-untyped]

# System prompt events
SYSTEM_PROMPT_CREATED = "system_prompt.created"
SYSTEM_PROMPT_UPDATED = "system_prompt.updated"
SYSTEM_PROMPT_DELETED = "system_prompt.deleted"


def build_system_prompt_created_event(
    prompt: SystemPromptModel,
    created_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for system prompt creation."""
    prompt_schema = SystemPromptSchema.model_validate(prompt)
    event_data: dict[str, object] = {
        "system_prompt": prompt_schema.model_dump(mode="json"),
    }
    if created_by_id is not None:
        event_data["created_by_id"] = str(created_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(SYSTEM_PROMPT_CREATED),
        event_data=event_data,
        subject=f"/system-prompts/{prompt.id}",
        user_id=str(created_by_id) if created_by_id else "",
        labels={"system_prompt_id": str(prompt.id)},
        tags=[f"system_prompt_id:{prompt.id}"],
    )


def build_system_prompt_updated_event(
    prompt: SystemPromptModel,
    updated_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for system prompt update."""
    prompt_schema = SystemPromptSchema.model_validate(prompt)
    event_data: dict[str, object] = {
        "system_prompt": prompt_schema.model_dump(mode="json"),
    }
    if updated_by_id is not None:
        event_data["updated_by_id"] = str(updated_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(SYSTEM_PROMPT_UPDATED),
        event_data=event_data,
        subject=f"/system-prompts/{prompt.id}",
        user_id=str(updated_by_id) if updated_by_id else "",
        labels={"system_prompt_id": str(prompt.id)},
        tags=[f"system_prompt_id:{prompt.id}"],
    )


def build_system_prompt_deleted_event(
    prompt: SystemPromptModel,
    deleted_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for system prompt deletion."""
    prompt_schema = SystemPromptSchema.model_validate(prompt)
    event_data: dict[str, object] = {
        "system_prompt": prompt_schema.model_dump(mode="json"),
    }
    if deleted_by_id is not None:
        event_data["deleted_by_id"] = str(deleted_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(SYSTEM_PROMPT_DELETED),
        event_data=event_data,
        subject=f"/system-prompts/{prompt.id}",
        user_id=str(deleted_by_id) if deleted_by_id else "",
        labels={"system_prompt_id": str(prompt.id)},
        tags=[f"system_prompt_id:{prompt.id}"],
    )
