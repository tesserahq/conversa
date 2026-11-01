"""Keeps local users in step with the user.* events Identies publishes."""

from typing import Callable

from tessera_sdk.infra.events.event import Event

from app.core.identies_events import IdentiesEventNames
from app.infra.logging_config import get_logger
from app.schemas.identies_user import IdentiesUser
from app.services.user_provisioner import UserProvisioner

logger = get_logger("identies_user_events")


class IdentiesUserEventHandler:
    """Registers human users as Identies announces them.

    A created user is synced straight away, so its context is ready before its
    first chat. Agents and service accounts are skipped: chat is for humans.
    """

    def __init__(
        self,
        users: UserProvisioner,
        enqueue_sync: Callable[[str], object],
        event_names: IdentiesEventNames,
    ) -> None:
        self._users = users
        self._enqueue_sync = enqueue_sync
        self._created = event_names.user_created
        self._handled = frozenset({event_names.user_created, event_names.user_updated})

    def handles(self, event_type: str) -> bool:
        return event_type in self._handled

    def handle(self, event: Event) -> None:
        identies_user = IdentiesUser.model_validate(event.event_data.get("user", {}))
        if not identies_user.is_human:
            logger.info("Skipping non-human user event %s", event.id)
            return

        self._users.sync(identies_user)
        logger.info("Registered user %s from %s", identies_user.id, event.event_type)

        if event.event_type == self._created:
            self._enqueue_sync(str(identies_user.id))
