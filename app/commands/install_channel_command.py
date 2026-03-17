"""Command to record a new channel workspace installation and publish an event."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.channel_installation_events import (
    build_channel_installation_created_event,
)
from app.repositories.channel_installation_repository import (
    ChannelInstallationRepository,
)
from app.repositories.user_repository import UserRepository
from tessera_sdk.infra.events.nats_router import NatsEventPublisher

logger = logging.getLogger(__name__)


class InstallChannelCommand:
    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ) -> None:
        self.db = db
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )

    def execute(
        self,
        *,
        channel: str,
        account_id: str,
        sensitive_data: Dict[str, Any],
        account_name: Optional[str] = None,
        bot_user_id: Optional[str] = None,
        installer_user_id: Optional[str] = None,
        scopes: Optional[str] = None,
        tessera_user_id: Optional[str] = None,
    ) -> None:
        created_by_id: Optional[UUID] = None
        if tessera_user_id:
            user_repo = UserRepository(self.db)
            user = user_repo.get_user(UUID(tessera_user_id))
            if user:
                created_by_id = user.id

        repo = ChannelInstallationRepository(self.db)
        installation = repo.upsert(
            channel=channel,
            account_id=account_id,
            sensitive_data=sensitive_data,
            account_name=account_name,
            bot_user_id=bot_user_id,
            installer_user_id=installer_user_id,
            scopes=scopes,
            created_by_id=created_by_id,
        )

        event = build_channel_installation_created_event(installation)
        try:
            self.nats_publisher.publish_sync(event, event.event_type)
        except Exception:
            logger.exception("Failed to publish channel_installation.created event")
