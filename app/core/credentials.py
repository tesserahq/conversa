"""Credential registry, validation, and encryption for context source auth."""

from __future__ import annotations

import json
from typing import Any, Dict, Type

from cryptography.fernet import Fernet
from pydantic import BaseModel

from app.constants.credentials import CredentialType
from app.schemas.credential import (
    ApiKeyModel,
    BasicAuthModel,
    BearerAuthModel,
    CredentialField,
    CredentialTypeInfo,
    M2mIdentiesModel,
)
from app.config import get_settings


def _get_fernet() -> Fernet:
    """Get a Fernet instance with the credential master key."""
    settings = get_settings()
    key = settings.credential_master_key or settings.fernet_key
    if not key:
        raise ValueError(
            "CREDENTIAL_MASTER_KEY or FERNET_KEY must be set for credential encryption"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt_value(value: bytes) -> bytes:
    """Encrypt a value using the master key."""
    return _get_fernet().encrypt(value)


def _decrypt_value(value: bytes) -> bytes:
    """Decrypt a value using the master key."""
    return _get_fernet().decrypt(value)


# Field definitions per credential type
bearer_auth_fields = [
    CredentialField(
        name="token",
        label="Bearer Token",
        type="string",
        input_type="password",
        help="Bearer token for API authentication",
        required=True,
    ),
]

basic_auth_fields = [
    CredentialField(
        name="username",
        label="Username",
        type="string",
        input_type="text",
        help="Username for basic authentication",
        required=True,
    ),
    CredentialField(
        name="password",
        label="Password",
        type="string",
        input_type="password",
        help="Password for basic authentication",
        required=True,
    ),
]

api_key_fields = [
    CredentialField(
        name="header_name",
        label="Header Name",
        type="string",
        input_type="text",
        help="HTTP header name (e.g. X-Api-Key)",
        required=False,
    ),
    CredentialField(
        name="api_key",
        label="API Key",
        type="string",
        input_type="password",
        help="API key value",
        required=True,
    ),
]

credential_registry: Dict[CredentialType, CredentialTypeInfo] = {
    CredentialType.BEARER_AUTH: CredentialTypeInfo(
        type_name=CredentialType.BEARER_AUTH,
        display_name="Bearer Authentication",
        fields=bearer_auth_fields,
    ),
    CredentialType.BASIC_AUTH: CredentialTypeInfo(
        type_name=CredentialType.BASIC_AUTH,
        display_name="Basic Authentication",
        fields=basic_auth_fields,
    ),
    CredentialType.API_KEY: CredentialTypeInfo(
        type_name=CredentialType.API_KEY,
        display_name="API Key",
        fields=api_key_fields,
    ),
    CredentialType.M2M_IDENTIES: CredentialTypeInfo(
        type_name=CredentialType.M2M_IDENTIES,
        display_name="M2M Identies",
        fields=[],
    ),
}

credential_models: Dict[CredentialType, Type[BaseModel]] = {
    CredentialType.BEARER_AUTH: BearerAuthModel,
    CredentialType.BASIC_AUTH: BasicAuthModel,
    CredentialType.API_KEY: ApiKeyModel,
    CredentialType.M2M_IDENTIES: M2mIdentiesModel,
}


def get_credential_type(type_name: str) -> CredentialTypeInfo:
    """Get a credential type by name."""
    try:
        cred_type = CredentialType(type_name)
    except ValueError:
        raise ValueError(f"Unknown credential type: {type_name}") from None
    if cred_type not in credential_registry:
        raise ValueError(f"Unknown credential type: {type_name}")
    return credential_registry[cred_type]


def validate_credential_fields(type_name: str, fields: Dict[str, Any]) -> None:
    """Validate credential fields against their model."""
    try:
        cred_type = CredentialType(type_name)
    except ValueError:
        raise ValueError(f"Unknown credential type: {type_name}") from None
    if cred_type not in credential_models:
        raise ValueError(f"Unknown credential type: {type_name}")

    model = credential_models[cred_type]
    try:
        model(**fields)
    except Exception as e:
        raise ValueError(f"Invalid credential fields: {str(e)}") from e


def encrypt_credential_fields(fields: Dict[str, Any]) -> bytes:
    """Encrypt credential fields."""
    plaintext = json.dumps(fields).encode()
    return _encrypt_value(plaintext)


def decrypt_credential_fields(encrypted_data: bytes) -> Dict[str, Any]:
    """Decrypt credential fields."""
    plaintext = _decrypt_value(encrypted_data)
    return json.loads(plaintext)
