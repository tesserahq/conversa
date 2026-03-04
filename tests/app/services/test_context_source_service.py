"""Tests for ContextSourceService."""

from uuid import uuid4

import pytest

from app.schemas.context_source import ContextSourceCreate, ContextSourceUpdate
from app.services.context_source_service import ContextSourceService


def test_create_context_source(db, setup_credential):
    """Create a context source and verify it is stored."""
    svc = ContextSourceService(db)
    data = ContextSourceCreate(
        source_id="linden-api",
        display_name="Linden API",
        base_url="https://api.linden.example.com",
        credential_id=setup_credential.id,
        capabilities=None,
        poll_interval_seconds=1800,
        enabled=True,
    )
    source = svc.create_context_source(data)
    assert source.id is not None
    assert source.source_id == "linden-api"
    assert source.display_name == "Linden API"
    assert source.base_url == "https://api.linden.example.com"
    assert source.credential_id == setup_credential.id


def test_create_context_source_duplicate_source_id_fails(db, setup_context_source):
    """Creating with duplicate source_id raises ValueError."""
    svc = ContextSourceService(db)
    data = ContextSourceCreate(
        source_id=setup_context_source.source_id,
        display_name="Other",
        base_url="https://other.example.com",
    )
    with pytest.raises(ValueError, match="already exists"):
        svc.create_context_source(data)


def test_get_context_source(db, setup_context_source):
    """Fetch context source by ID."""
    svc = ContextSourceService(db)
    found = svc.get_context_source(setup_context_source.id)
    assert found is not None
    assert found.id == setup_context_source.id
    assert found.source_id == setup_context_source.source_id


def test_get_context_source_by_source_id(db, setup_context_source):
    """Fetch context source by source_id string."""
    svc = ContextSourceService(db)
    found = svc.get_context_source_by_source_id(setup_context_source.source_id)
    assert found is not None
    assert found.id == setup_context_source.id


def test_get_context_source_not_found(db):
    """Fetch non-existent context source returns None."""
    svc = ContextSourceService(db)
    found = svc.get_context_source(uuid4())
    assert found is None


def test_update_context_source(db, setup_context_source):
    """Update context source fields."""
    svc = ContextSourceService(db)
    data = ContextSourceUpdate(
        display_name="Updated Display",
        poll_interval_seconds=7200,
    )
    updated = svc.update_context_source(setup_context_source.id, data)
    assert updated is not None
    assert updated.display_name == "Updated Display"
    assert updated.poll_interval_seconds == 7200


def test_delete_context_source(db, setup_context_source):
    """Soft delete context source."""
    svc = ContextSourceService(db)
    result = svc.delete_context_source(setup_context_source.id)
    assert result is True
    found = svc.get_context_source(setup_context_source.id)
    assert found is None


def test_search_context_sources(db, setup_context_source):
    """Search context sources by filter."""
    svc = ContextSourceService(db)
    results = svc.search({"enabled": True})
    assert len(results) >= 1
    ids = [s.id for s in results]
    assert setup_context_source.id in ids
