"""Tests for CredentialApplier."""

from uuid import uuid4

import pytest

from app.constants.credentials import CredentialType
from app.schemas.credential import CredentialCreate
from app.repositories.credential_repository import CredentialRepository
from app.repositories.credential_applier import CredentialApplier


def test_apply_bearer(db, setup_user):
    """apply() adds Bearer header for bearer_auth credential."""
    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="bearer-test",
            type=CredentialType.BEARER_AUTH,
            fields={"token": "my-secret-token"},
        ),
        created_by_id=None,
    )
    applier = CredentialApplier(db)
    headers = applier.apply(cred.id)
    assert headers["Authorization"] == "Bearer my-secret-token"


def test_apply_default_m2m_when_credential_id_none(db):
    """apply() with credential_id=None injects default M2M token."""
    applier = CredentialApplier(db, m2m_token_provider=lambda: "m2m-token-xyz")
    headers = applier.apply(credential_id=None)
    assert headers["Authorization"] == "Bearer m2m-token-xyz"


def test_apply_default_m2m_raises_when_provider_returns_none(db):
    """apply() with credential_id=None raises when provider returns None."""
    applier = CredentialApplier(db, m2m_token_provider=lambda: None)
    with pytest.raises(ValueError, match="Default M2M auth requires an M2M token"):
        applier.apply(credential_id=None)


def test_apply_m2m_identies_uses_provider(db, setup_user):
    """apply() for M2M_IDENTIES uses the M2M token provider."""
    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="m2m-test",
            type=CredentialType.M2M_IDENTIES,
            fields={},
        ),
        created_by_id=setup_user.id,
    )
    applier = CredentialApplier(db, m2m_token_provider=lambda: "m2m-identies-token")
    headers = applier.apply(cred.id)
    assert headers["Authorization"] == "Bearer m2m-identies-token"


def test_apply_for_user_none_credential_adds_no_auth(db):
    """apply_for_user() returns headers unchanged when credential_id is None."""
    applier = CredentialApplier(db, m2m_token_provider=lambda: "unused")
    headers = applier.apply_for_user(
        credential_id=None,
        headers={"X-Request-Id": "abc"},
    )
    assert headers == {"X-Request-Id": "abc"}


def test_apply_for_user_bearer_credential(db, setup_user):
    """apply_for_user() supports static bearer credentials."""
    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="mcp-bearer",
            type=CredentialType.BEARER_AUTH,
            fields={"token": "mcp-token"},
        ),
        created_by_id=setup_user.id,
    )
    applier = CredentialApplier(db)
    headers = applier.apply_for_user(credential_id=cred.id)
    assert headers["Authorization"] == "Bearer mcp-token"


class _FakeDelegatedTokenRepo:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_access_token(self, **kwargs):
        self.calls.append(kwargs)
        return "delegated-token-123"


def test_apply_for_user_delegated_exchange(db, setup_user):
    """Delegated exchange calls the delegated token repo with user context."""
    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="delegated",
            type=CredentialType.DELEGATED_IDENTIES_EXCHANGE,
            fields={"audience": "linden", "scopes": ["mcp:tools:execute"]},
        ),
        created_by_id=setup_user.id,
    )

    fake_delegated = _FakeDelegatedTokenRepo()
    applier = CredentialApplier(
        db,
        m2m_token_provider=lambda: "unused",
        delegated_token_repo=fake_delegated,
    )
    headers = applier.apply_for_user(
        credential_id=cred.id,
        user_id=setup_user.id,
        context={"channel": "telegram"},
    )

    assert headers["Authorization"] == "Bearer delegated-token-123"
    assert len(fake_delegated.calls) == 1
    assert fake_delegated.calls[0]["audience"] == "linden"
    assert fake_delegated.calls[0]["scopes"] == ["mcp:tools:execute"]


def test_apply_for_user_delegated_requires_user_id(db, setup_user):
    """Delegated exchange raises when user_id is not provided."""
    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="delegated-no-user",
            type=CredentialType.DELEGATED_IDENTIES_EXCHANGE,
            fields={"audience": "linden", "scopes": "mcp:tools:execute"},
        ),
        created_by_id=setup_user.id,
    )
    applier = CredentialApplier(
        db,
        delegated_token_repo=_FakeDelegatedTokenRepo(),
        m2m_token_provider=lambda: "unused",
    )
    with pytest.raises(
        ValueError, match="Delegated Identies exchange requires user_id"
    ):
        applier.apply_for_user(credential_id=cred.id)


def test_delegated_token_repo_constructed_lazily(db, setup_user, monkeypatch):
    """Delegated token repo is constructed only on first delegated execution path."""
    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="delegated-lazy",
            type=CredentialType.DELEGATED_IDENTIES_EXCHANGE,
            fields={"audience": "linden", "scopes": ["mcp:tools:execute"]},
        ),
        created_by_id=setup_user.id,
    )

    constructed = []
    calls = []

    class _TrackingRepo:
        def __init__(self, **_):
            constructed.append(True)

        def get_access_token(self, **kwargs):
            calls.append(kwargs)
            return "tok"

    import app.repositories.credential_applier as credential_applier_module

    monkeypatch.setattr(
        credential_applier_module, "MCPDelegatedTokenRepository", _TrackingRepo
    )

    # Instantiate applier — delegated repo should not be constructed yet.
    applier = CredentialApplier(
        db, delegated_token_repo=None, m2m_token_provider=lambda: "unused"
    )
    assert constructed == []

    headers = applier.apply_for_user(
        credential_id=cred.id, user_id=setup_user.id, context={"channel": "telegram"}
    )
    assert headers["Authorization"] == "Bearer tok"
    assert constructed == [True]
    assert len(calls) == 1

    # Repo instance should be cached; second call should not reconstruct.
    applier.apply_for_user(
        credential_id=cred.id, user_id=setup_user.id, context={"channel": "telegram"}
    )
    assert constructed == [True]
    assert len(calls) == 2


def test_m2m_token_provider_not_called_for_bearer(db, setup_user):
    """M2M token provider is never invoked when credential type is bearer."""
    called = []

    def _tracking_provider():
        called.append(True)
        return "should-not-be-called"

    repo = CredentialRepository(db)
    cred = repo.create_credential(
        CredentialCreate(
            name="bearer-lazy",
            type=CredentialType.BEARER_AUTH,
            fields={"token": "static-token"},
        ),
        created_by_id=setup_user.id,
    )
    applier = CredentialApplier(db, m2m_token_provider=_tracking_provider)
    applier.apply(cred.id)

    assert called == []
