"""Lookups of users in Identies, the source of truth for who exists."""

from typing import Callable, Protocol
from uuid import UUID

from tessera_sdk.clients.identies import IdentiesClient
from tessera_sdk.clients.identies.exceptions import IdentiesNotFoundError

from app.core.identies_client import build_identies_client
from app.schemas.identies_user import IdentiesUser


class IdentiesDirectory(Protocol):
    """Finds a single user in Identies. Returns None when Identies has no such user."""

    def get_user(self, user_id: UUID) -> IdentiesUser | None: ...


class IdentiesApiDirectory:
    """IdentiesDirectory backed by the Identies API."""

    def __init__(
        self,
        client_factory: Callable[[], IdentiesClient] = build_identies_client,
    ) -> None:
        self._client_factory = client_factory

    def get_user(self, user_id: UUID) -> IdentiesUser | None:
        try:
            response = self._client_factory().get_internal_user(str(user_id))
        except IdentiesNotFoundError:
            return None
        return IdentiesUser.model_validate(response.model_dump())
