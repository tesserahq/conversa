"""
Utilities for building credential-related CloudEvents payloads.
"""

from __future__ import annotations

from uuid import UUID

from app.models.credential import Credential as CredentialModel
from app.schemas.credential import CredentialRead as CredentialSchema
from tessera_sdk.infra.events.event import Event, event_source, event_type  # type: ignore[import-untyped]

# Credential events
CREDENTIAL_CREATED = "credential.created"
CREDENTIAL_UPDATED = "credential.updated"
CREDENTIAL_DELETED = "credential.deleted"


def build_credential_created_event(
    credential: CredentialModel,
    created_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for credential creation."""
    credential_schema = CredentialSchema.model_validate(credential)
    event_data: dict[str, object] = {
        "credential": credential_schema.model_dump(mode="json"),
    }
    if created_by_id is not None:
        event_data["created_by_id"] = str(created_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(CREDENTIAL_CREATED),
        event_data=event_data,
        subject=f"/credentials/{credential.id}",
        user_id=str(created_by_id) if created_by_id else "",
        labels={"credential_id": str(credential.id)},
        tags=[f"credential_id:{credential.id}"],
    )
