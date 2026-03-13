"""Tests for CredentialService."""

from uuid import uuid4

import pytest

from app.constants.credentials import CredentialType
from app.schemas.credential import CredentialCreate, CredentialUpdate
from app.repositories.credential_repository import CredentialRepository


def test_create_credential(db, setup_user):
    """Create a credential and verify it is stored."""
    svc = CredentialRepository(db)
    data = CredentialCreate(
        name="test-bearer",
        type=CredentialType.BEARER_AUTH,
        fields={"token": "secret-token-123"},
    )
    credential = svc.create_credential(data, created_by_id=setup_user.id)
    assert credential.id is not None
    assert credential.name == "test-bearer"
    assert credential.type == CredentialType.BEARER_AUTH
    assert credential.encrypted_data is not None
    assert credential.created_by_id == setup_user.id


def test_create_credential_fields_persisted_and_retrievable(db, setup_user):
    """Create a credential with fields and verify they are saved and returned by get_credential_fields."""
    svc = CredentialRepository(db)
    fields = {"audience": "api://resource", "scopes": ["read", "write"]}
    data = CredentialCreate(
        name="MCP",
        type=CredentialType.DELEGATED_IDENTIES_EXCHANGE,
        fields=fields,
    )
    credential = svc.create_credential(data, created_by_id=setup_user.id)
    assert credential.id is not None
    retrieved = svc.get_credential_fields(credential.id)
    assert retrieved is not None
    assert retrieved["audience"] == "api://resource"
    assert retrieved["scopes"] == ["read", "write"]


def test_get_credential(db, setup_credential):
    """Fetch credential by ID."""
    svc = CredentialRepository(db)
    found = svc.get_credential(setup_credential.id)
    assert found is not None
    assert found.id == setup_credential.id
    assert found.name == setup_credential.name


def test_get_credential_not_found(db):
    """Fetch non-existent credential returns None."""
    svc = CredentialRepository(db)
    found = svc.get_credential(uuid4())
    assert found is None


def test_get_credentials_list(db, setup_credential):
    """List credentials with pagination."""
    svc = CredentialRepository(db)
    credentials = svc.get_credentials(skip=0, limit=10)
    assert len(credentials) >= 1
    ids = [c.id for c in credentials]
    assert setup_credential.id in ids


def test_update_credential(db, setup_credential):
    """Update credential name and fields."""
    svc = CredentialRepository(db)
    data = CredentialUpdate(name="updated-name", fields={"token": "new-token"})
    updated = svc.update_credential(setup_credential.id, data)
    assert updated is not None
    assert updated.name == "updated-name"
    fields = svc.get_credential_fields(setup_credential.id)
    assert fields == {"token": "new-token"}


def test_delete_credential(db, setup_credential):
    """Soft delete credential."""
    svc = CredentialRepository(db)
    result = svc.delete_credential(setup_credential.id)
    assert result is True
    found = svc.get_credential(setup_credential.id)
    assert found is None  # soft delete filter hides it


def test_validate_credential_fields_rejects_invalid(db, setup_user):
    """Create with invalid fields raises ValueError."""
    svc = CredentialRepository(db)
    data = CredentialCreate(
        name="bad",
        type=CredentialType.BEARER_AUTH,
        fields={},  # missing token
    )
    with pytest.raises(ValueError, match="Invalid credential fields"):
        svc.create_credential(data, created_by_id=setup_user.id)


def test_apply_credentials_bearer(db, setup_user):
    """apply_credentials adds Bearer header for bearer_auth."""
    svc = CredentialRepository(db)
    # Create credential with known token for apply test
    data = CredentialCreate(
        name="bearer-test",
        type=CredentialType.BEARER_AUTH,
        fields={"token": "my-secret-token"},
    )
    cred = svc.create_credential(data, created_by_id=None)
    headers = svc.apply_credentials(cred.id)
    assert headers["Authorization"] == "Bearer my-secret-token"


def test_apply_credentials_default_m2m_when_credential_id_none(db):
    """apply_credentials with credential_id=None uses default M2M via provider."""
    svc = CredentialRepository(db, m2m_token_provider=lambda: "m2m-token-xyz")
    headers = svc.apply_credentials(credential_id=None)
    assert headers["Authorization"] == "Bearer m2m-token-xyz"


def test_apply_credentials_m2m_identies_uses_provider(db, setup_user):
    """apply_credentials for M2M_IDENTIES uses default M2M token from provider."""
    svc = CredentialRepository(db, m2m_token_provider=lambda: "m2m-identies-token")
    data = CredentialCreate(
        name="m2m-test",
        type=CredentialType.M2M_IDENTIES,
        fields={},
    )
    cred = svc.create_credential(data, created_by_id=setup_user.id)
    headers = svc.apply_credentials(cred.id)
    assert headers["Authorization"] == "Bearer m2m-identies-token"


def test_apply_credentials_default_m2m_raises_when_provider_returns_none(db):
    """apply_credentials with credential_id=None raises when provider returns None."""
    svc = CredentialRepository(db, m2m_token_provider=lambda: None)
    with pytest.raises(ValueError, match="Default M2M auth requires an M2M token"):
        svc.apply_credentials(credential_id=None)


class _FakeDelegatedTokenService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_access_token(self, **kwargs):
        self.calls.append(kwargs)
        return "delegated-token-123"


def test_apply_credentials_with_context_with_none_credential_adds_no_auth(db):
    """MCP credential application keeps headers unchanged when credential_id is None."""
    svc = CredentialRepository(db, m2m_token_provider=lambda: "unused")
    headers = svc.apply_credentials_with_context(
        credential_id=None,
        headers={"X-Request-Id": "abc"},
    )
    assert headers == {"X-Request-Id": "abc"}


def test_apply_credentials_with_context_with_bearer_credential(db, setup_user):
    """MCP credential application supports static bearer credentials."""
    svc = CredentialRepository(db)
    credential = svc.create_credential(
        CredentialCreate(
            name="mcp-bearer",
            type=CredentialType.BEARER_AUTH,
            fields={"token": "mcp-token"},
        ),
        created_by_id=setup_user.id,
    )
    headers = svc.apply_credentials_with_context(credential_id=credential.id)
    assert headers["Authorization"] == "Bearer mcp-token"


def test_apply_credentials_with_context_delegated_exchange(db, setup_user):
    """Delegated exchange credentials call delegated token provider with user context."""
    delegated = _FakeDelegatedTokenService()
    svc = CredentialRepository(
        db,
        delegated_token_service=delegated,
        m2m_token_provider=lambda: "unused",
    )
    credential = svc.create_credential(
        CredentialCreate(
            name="delegated",
            type=CredentialType.DELEGATED_IDENTIES_EXCHANGE,
            fields={"audience": "linden", "scopes": ["mcp:tools:execute"]},
        ),
        created_by_id=setup_user.id,
    )

    headers = svc.apply_credentials_with_context(
        credential_id=credential.id,
        user_id=setup_user.id,
        context={"channel": "telegram"},
    )

    assert headers["Authorization"] == "Bearer delegated-token-123"
    assert len(delegated.calls) == 1
    assert delegated.calls[0]["audience"] == "linden"
    assert delegated.calls[0]["scopes"] == ["mcp:tools:execute"]


def test_apply_credentials_with_context_delegated_requires_user_id(db, setup_user):
    """Delegated exchange credentials require user_id in request context."""
    svc = CredentialRepository(
        db,
        delegated_token_service=_FakeDelegatedTokenService(),
        m2m_token_provider=lambda: "unused",
    )
    credential = svc.create_credential(
        CredentialCreate(
            name="delegated-no-user",
            type=CredentialType.DELEGATED_IDENTIES_EXCHANGE,
            fields={"audience": "linden", "scopes": "mcp:tools:execute"},
        ),
        created_by_id=setup_user.id,
    )

    with pytest.raises(
        ValueError, match="Delegated Identies exchange requires user_id"
    ):
        svc.apply_credentials_with_context(credential_id=credential.id)
