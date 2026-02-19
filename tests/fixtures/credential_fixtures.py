"""Fixtures for credential model."""

import pytest

from app.constants.credentials import CredentialType
from app.core.credentials import encrypt_credential_fields
from app.models.credential import Credential


@pytest.fixture(scope="function")
def setup_credential(db, faker, setup_user):
    """
    Create a credential (bearer_auth type) for testing.
    """
    fields = {"token": faker.sha256()}
    encrypted_data = encrypt_credential_fields(fields)

    credential = Credential(
        name=faker.word() + "-cred",
        type=CredentialType.BEARER_AUTH,
        encrypted_data=encrypted_data,
        created_by_id=setup_user.id,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


@pytest.fixture(scope="function")
def setup_credential_basic_auth(db, faker, setup_user):
    """Create a credential with basic auth type."""
    fields = {"username": faker.user_name(), "password": faker.password()}
    encrypted_data = encrypt_credential_fields(fields)

    credential = Credential(
        name=faker.word() + "-basic",
        type=CredentialType.BASIC_AUTH,
        encrypted_data=encrypted_data,
        created_by_id=setup_user.id,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential
