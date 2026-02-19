"""Credential types for context source auth."""

from enum import StrEnum


class CredentialType(StrEnum):
    """Supported credential types for context pack auth."""

    BEARER_AUTH = "bearer_auth"
    BASIC_AUTH = "basic_auth"
    API_KEY = "api_key"
    M2M_IDENTIES = "m2m_identies"
