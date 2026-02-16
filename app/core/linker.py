from tessera_sdk.identies import IdentiesClient
from tessera_sdk.identies.schemas.external_account_response import CheckResponse
from tessera_sdk.identies.schemas.user_response import UserResponse
from tessera_sdk.utils.m2m_token import M2MTokenClient
from tessera_sdk.utils.cache import Cache
from app.schemas.user import User
from app.services.user_service import UserService
from app.utils.db.db_session_helper import db_session
from uuid import UUID
from app.schemas.user import UserOnboard

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
            # We need to fetch the user from Identies. Users in conversa
            # are being used as a cache for Identies users.
            self._fetch_user(linked_response.user.id)
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
    
    def _fetch_user(
        self,
        user_id: UUID,
    ) -> User:
        """
        Fetch a user from Identies.

        Args:
            user_id: The ID of the user

        Returns:
            User: The user
        """
        with db_session() as db:
            user_service = UserService(db=db)
            # If the user doesn't exist, we need to fetch it from Identies
            user = user_service.get_user(user_id)
            if user:
                return user
            
            m2m_token = self._get_m2m_token()

            identies_client = IdentiesClient(
                api_token=m2m_token,
            )

            identies_user = identies_client.get_internal_user(user_id)

            user = UserOnboard(
                id=identies_user.id,
                email=identies_user.email,
                service_account=identies_user.service_account,
                preferred_name=identies_user.preferred_name,
                first_name=identies_user.first_name,
                last_name=identies_user.last_name,
                avatar_url=identies_user.avatar_url,
                provider=identies_user.provider,
                verified=identies_user.verified,
                verified_at=identies_user.verified_at,
                confirmed_at=identies_user.confirmed_at,
                external_id=identies_user.external_id,
            )

            return user_service.onboard_user(user)

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
