"""Construction of the Identies API client, shared by every component that calls Identies."""

from tessera_sdk.clients.identies import IdentiesClient
from tessera_sdk.infra import AuthTokenProvider


def build_identies_client() -> IdentiesClient:
    """Build an Identies client with the resolved auth token.

    The token is taken from IDENTIES_API_KEY first, then from the Auth0 M2M fallback.
    """
    return IdentiesClient(api_token=AuthTokenProvider().get_token())
