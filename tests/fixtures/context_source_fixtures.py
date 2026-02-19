"""Fixtures for context source and context source state models."""

import pytest

from app.models.context_source import ContextSource, ContextSourceState


@pytest.fixture(scope="function")
def setup_context_source(db, faker):
    """Create a context source for testing (source_id must be lowercase alphanumeric + hyphens)."""
    source_id = f"test-{faker.lexify('??????').lower()}"
    source = ContextSource(
        source_id=source_id,
        display_name=faker.company(),
        base_url="https://api.example.com",
        credential_id=None,
        capabilities={"supports_etag": True, "supports_since_cursor": False},
        poll_interval_seconds=3600,
        enabled=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@pytest.fixture(scope="function")
def setup_context_source_with_credential(db, faker, setup_credential):
    """Create a context source linked to a credential."""
    source = ContextSource(
        source_id=f"linden-{faker.lexify('??????').lower()}",
        display_name=faker.company(),
        base_url="https://api.example.com",
        credential_id=setup_credential.id,
        capabilities={"supports_etag": True, "supports_since_cursor": True},
        poll_interval_seconds=1800,
        enabled=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@pytest.fixture(scope="function")
def setup_context_source_state(db, setup_context_source, setup_user):
    """Create context source state for a source and user."""
    state = ContextSourceState(
        source_id=setup_context_source.id,
        user_id=setup_user.id,
        last_success_at=None,
        last_attempt_at=None,
        last_error=None,
        etag=None,
        since_cursor=None,
        next_run_at=None,
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state
