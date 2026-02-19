"""Tests for CredentialService."""

from uuid import uuid4

import pytest

from app.constants.credentials import CredentialType
from app.schemas.credential import CredentialCreate, CredentialUpdate
from app.services.credential_service import CredentialService


def test_create_credential(db, setup_user):
    """Create a credential and verify it is stored."""
    svc = CredentialService(db)
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


def test_get_credential(db, setup_credential):
    """Fetch credential by ID."""
    svc = CredentialService(db)
    found = svc.get_credential(setup_credential.id)
    assert found is not None
    assert found.id == setup_credential.id
    assert found.name == setup_credential.name


def test_get_credential_not_found(db):
    """Fetch non-existent credential returns None."""
    svc = CredentialService(db)
    found = svc.get_credential(uuid4())
    assert found is None


def test_get_credentials_list(db, setup_credential):
    """List credentials with pagination."""
    svc = CredentialService(db)
    credentials = svc.get_credentials(skip=0, limit=10)
    assert len(credentials) >= 1
    ids = [c.id for c in credentials]
    assert setup_credential.id in ids


def test_update_credential(db, setup_credential):
    """Update credential name and fields."""
    svc = CredentialService(db)
    data = CredentialUpdate(name="updated-name", fields={"token": "new-token"})
    updated = svc.update_credential(setup_credential.id, data)
    assert updated is not None
    assert updated.name == "updated-name"
    fields = svc.get_credential_fields(setup_credential.id)
    assert fields == {"token": "new-token"}


def test_delete_credential(db, setup_credential):
    """Soft delete credential."""
    svc = CredentialService(db)
    result = svc.delete_credential(setup_credential.id)
    assert result is True
    found = svc.get_credential(setup_credential.id)
    assert found is None  # soft delete filter hides it


def test_validate_credential_fields_rejects_invalid(db, setup_user):
    """Create with invalid fields raises ValueError."""
    svc = CredentialService(db)
    data = CredentialCreate(
        name="bad",
        type=CredentialType.BEARER_AUTH,
        fields={},  # missing token
    )
    with pytest.raises(ValueError, match="Invalid credential fields"):
        svc.create_credential(data, created_by_id=setup_user.id)


def test_apply_credentials_bearer(db, setup_user):
    """apply_credentials adds Bearer header for bearer_auth."""
    svc = CredentialService(db)
    # Create credential with known token for apply test
    data = CredentialCreate(
        name="bearer-test",
        type=CredentialType.BEARER_AUTH,
        fields={"token": "my-secret-token"},
    )
    cred = svc.create_credential(data, created_by_id=None)
    headers = svc.apply_credentials(cred.id)
    assert headers["Authorization"] == "Bearer my-secret-token"
