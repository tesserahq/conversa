from tessera_sdk.identies import IdentiesClient
from tessera_sdk.identies.schemas.external_account_response import CheckResponse
from tessera_sdk.identies.schemas.user_response import UserResponse
from tessera_sdk.utils.m2m_token import M2MTokenClient
from tessera_sdk.utils.cache import Cache
from app.schemas.user import User

LINKED_CACHE_TTL = 86400  # 24 hours
LINKED_CACHE_NAMESPACE = "identies_linked"


class Linker:
    def __init__(self) -> None:
        self._linked_cache: Cache = Cache(namespace=LINKED_CACHE_NAMESPACE)

    def is_account_linked(self, channel: str, external_id: str) -> bool:
        """
        Check if the account is already linked in Identies.
        Uses cache first; only calls Identies on cache miss. Writes to cache when linked.
        """
        if self._in_cache(channel, external_id) is True:
            return True

        linked_response = self._check_identies(channel, external_id)

        if linked_response.linked is True:
            self._write_cache(channel, external_id, linked_response.user)
            return True
        return False

    def generate_link_token(self, channel: str, external_id: str) -> str:
        m2m_token = self._get_m2m_token()
        identies_client = IdentiesClient(api_token=m2m_token)
        link_response = identies_client.create_link_token(
            platform=channel,
            external_user_id=external_id,
        )

        return link_response.token

    def get_linked_user(self, channel: str, external_id: str) -> User | None:
        if self._in_cache(channel, external_id) is False:
            return None
        return self._read_cache(channel, external_id)

    def _check_identies(self, channel: str, external_id: str) -> CheckResponse:
        m2m_token = self._get_m2m_token()
        identies_client = IdentiesClient(api_token=m2m_token)
        check_response = identies_client.check_external_account(
            platform=channel,
            external_id=external_id,
        )
        return check_response

    def _get_m2m_token(self) -> str:
        """Get an M2M token for calling Identies."""
        return M2MTokenClient().get_token_sync().access_token

    def _linked_cache_key(self, channel: str, external_id: str) -> str:
        """Build cache key for linked external account."""
        return f"{channel}:{external_id}"

    def _in_cache(self, channel: str, external_id: str) -> bool:
        cache_key = self._linked_cache_key(channel, external_id)
        return self._linked_cache.read(cache_key) is not None

    def _write_cache(self, channel: str, external_id: str, user: UserResponse) -> None:
        user = User.model_validate(user)
        cache_key = self._linked_cache_key(channel, external_id)
        self._linked_cache.write(cache_key, user, ttl=LINKED_CACHE_TTL)

    def _read_cache(self, channel: str, external_id: str) -> User | None:
        cache_key = self._linked_cache_key(channel, external_id)
        user = self._linked_cache.read(cache_key)
        return User.model_validate(user) if user else None

    def _delete_cache(self, channel: str, external_id: str) -> None:
        cache_key = self._linked_cache_key(channel, external_id)
        self._linked_cache.delete(cache_key)
