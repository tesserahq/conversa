from tessera_sdk.clients.identies.schemas.external_account_response import CheckResponse
from tessera_sdk.clients.identies.schemas.user_response import UserResponse
from tessera_sdk.infra.cache import Cache

from app.core.identies_client import build_identies_client
from app.schemas.user import User
from app.services.user_provisioner import UserProvisioner

LINKED_CACHE_TTL = 86400  # 24 hours
LINKED_CACHE_NAMESPACE = "identies_linked"


class Linker:
    def __init__(self, users: UserProvisioner | None = None) -> None:
        self._linked_cache: Cache = Cache(namespace=LINKED_CACHE_NAMESPACE)
        self._users = users or UserProvisioner()

    def is_account_linked(self, channel: str, external_id: str) -> bool:
        """
        Check if the account is already linked in Identies.
        Uses cache first; only calls Identies on cache miss. Writes to cache when linked.
        """
        return self.get_or_resolve_linked_user(channel, external_id) is not None

    def generate_link_token(self, channel: str, external_id: str) -> str:
        identies_client = build_identies_client()
        link_response = identies_client.create_link_token(
            platform=channel,
            external_user_id=external_id,
        )

        return link_response.token

    def get_linked_user(self, channel: str, external_id: str) -> User | None:
        if self._in_cache(channel, external_id) is False:
            return None
        return self._read_cache(channel, external_id)

    def get_or_resolve_linked_user(self, channel: str, external_id: str) -> User | None:
        cached_user = self.get_linked_user(channel, external_id)
        if cached_user is not None:
            return cached_user

        linked_response = self._check_identies(channel, external_id)
        if linked_response.linked is False:
            return None

        # Registers the user locally if needed, then refreshes the Redis cache.
        if self._users.ensure_user(linked_response.user.id) is None:
            return None
        self._write_cache(channel, external_id, linked_response.user)
        return self._read_cache(channel, external_id)

    def _check_identies(self, channel: str, external_id: str) -> CheckResponse:
        identies_client = build_identies_client()
        check_response = identies_client.check_external_account(
            platform=channel,
            external_id=external_id,
        )
        return check_response

    def _linked_cache_key(self, channel: str, external_id: str) -> str:
        """Build cache key for linked external account."""
        return f"{channel}:{external_id}"

    def _in_cache(self, channel: str, external_id: str) -> bool:
        cache_key = self._linked_cache_key(channel, external_id)
        return self._linked_cache.read(cache_key) is not None

    def _write_cache(self, channel: str, external_id: str, user: UserResponse) -> None:
        user = User.model_validate(user)
        cache_key = self._linked_cache_key(channel, external_id)
        self._linked_cache.write(
            cache_key, user.model_dump(mode="json"), ttl=LINKED_CACHE_TTL
        )

    def _read_cache(self, channel: str, external_id: str) -> User | None:
        cache_key = self._linked_cache_key(channel, external_id)
        user = self._linked_cache.read(cache_key)
        return User.model_validate(user) if user else None

    def _delete_cache(self, channel: str, external_id: str) -> None:
        cache_key = self._linked_cache_key(channel, external_id)
        self._linked_cache.delete(cache_key)
