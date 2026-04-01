"""Command to create a credential."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.credential_events import build_credential_created_event
from app.models.credential import Credential
from app.schemas.credential import CredentialCreate
from app.repositories.credential_repository import CredentialRepository
from tessera_sdk.infra.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class CreateCredentialCommand:
    """
    Command to create a credential and publish credential.created event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.credential_service = CredentialRepository(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        data: CredentialCreate,
        created_by_id: Optional[UUID] = None,
    ) -> Credential:
        """
        Execute the command to create a credential and publish the event.

        Args:
            data: The credential creation data.
            created_by_id: Optional user ID of the creator.

        Returns:
            The created credential.

        Raises:
            ValueError: If credential validation fails.
        """
        credential = self.credential_service.create_credential(
            data,
            created_by_id=created_by_id,
        )
        self._publish_credential_created_event(credential, created_by_id)
        return credential

    def _publish_credential_created_event(
        self,
        credential: Credential,
        created_by_id: Optional[UUID],
    ) -> None:
        """Publish a credential.created event to NATS."""
        event = build_credential_created_event(credential, created_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing credential-created event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish credential-created event to NATS"
                )
