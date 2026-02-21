"""Tests for ContextSourceStateService."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.context_source import ContextSourceState
from app.services.context_source_state_service import ContextSourceStateService


def test_get_or_create_state_creates_when_none_exists(
    db, setup_context_source, setup_user
):
    """get_or_create_state creates a new state when none exists."""
    svc = ContextSourceStateService(db)
    state = svc.get_or_create_state(setup_context_source.id, setup_user.id)
    assert state is not None
    assert state.source_id == setup_context_source.id
    assert state.user_id == setup_user.id
    assert state.last_success_at is None
    assert state.etag is None


def test_get_or_create_state_returns_existing(db, setup_context_source_state):
    """get_or_create_state returns existing state when it exists."""
    existing = setup_context_source_state
    svc = ContextSourceStateService(db)
    state = svc.get_or_create_state(existing.source_id, existing.user_id)
    assert state.id == existing.id
    assert state.source_id == existing.source_id
    assert state.user_id == existing.user_id


def test_update_state_updates_fields(db, setup_context_source_state):
    """update_state updates only the provided fields."""
    state = setup_context_source_state
    svc = ContextSourceStateService(db)
    now = datetime.now(timezone.utc)
    new_etag = "etag-abc"
    new_error = "Some error"

    svc.update_state(
        state,
        last_success_at=now,
        last_attempt_at=now,
        etag=new_etag,
        last_error=new_error,
    )

    db.refresh(state)
    assert state.last_success_at is not None
    assert state.last_attempt_at is not None
    assert state.etag == new_etag
    assert state.last_error == new_error


def test_update_state_ignores_none_values(db, setup_context_source_state):
    """update_state does not overwrite with None when None is passed."""
    state = setup_context_source_state
    state.etag = "original-etag"
    db.commit()
    db.refresh(state)

    svc = ContextSourceStateService(db)
    svc.update_state(state, last_success_at=datetime.now(timezone.utc))

    db.refresh(state)
    assert state.etag == "original-etag"


def test_get_due_user_source_pairs_returns_pairs_with_no_state(
    db, setup_context_source, setup_user
):
    """get_due_user_source_pairs returns (source, user) when no state exists."""
    svc = ContextSourceStateService(db)
    pairs = svc.get_due_user_source_pairs(limit=500)
    assert len(pairs) >= 1
    source_ids = [s.id for s, _ in pairs]
    user_ids = [u.id for _, u in pairs]
    assert setup_context_source.id in source_ids
    assert setup_user.id in user_ids


def test_get_due_user_source_pairs_returns_pairs_when_next_run_at_past(
    db, setup_context_source, setup_user
):
    """get_due_user_source_pairs returns pairs when next_run_at is in the past."""
    svc = ContextSourceStateService(db)
    state = svc.get_or_create_state(setup_context_source.id, setup_user.id)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    svc.update_state(state, next_run_at=past)

    pairs = svc.get_due_user_source_pairs(limit=500)
    pair_source_user_ids = [(s.id, u.id) for s, u in pairs]
    assert (setup_context_source.id, setup_user.id) in pair_source_user_ids


def test_get_due_user_source_pairs_excludes_when_next_run_at_future(
    db, setup_context_source, setup_user
):
    """get_due_user_source_pairs excludes pairs when next_run_at is in the future."""
    svc = ContextSourceStateService(db)
    state = svc.get_or_create_state(setup_context_source.id, setup_user.id)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    svc.update_state(state, next_run_at=future)

    pairs = svc.get_due_user_source_pairs(limit=500)
    pair_source_user_ids = [(s.id, u.id) for s, u in pairs]
    assert (setup_context_source.id, setup_user.id) not in pair_source_user_ids


def test_get_due_user_source_pairs_respects_limit(
    db, setup_context_source, setup_user, setup_another_user
):
    """get_due_user_source_pairs respects the limit parameter."""
    svc = ContextSourceStateService(db)
    pairs = svc.get_due_user_source_pairs(limit=1)
    assert len(pairs) <= 1


def test_get_due_user_source_pairs_excludes_disabled_sources(
    db, setup_context_source, setup_user
):
    """get_due_user_source_pairs excludes disabled sources."""
    from app.services.context_source_service import ContextSourceService
    from app.schemas.context_source import ContextSourceUpdate

    # Disable the source
    source_svc = ContextSourceService(db)
    source_svc.update_context_source(
        setup_context_source.id,
        ContextSourceUpdate(enabled=False),
    )

    svc = ContextSourceStateService(db)
    pairs = svc.get_due_user_source_pairs(limit=500)
    source_ids = [s.id for s, _ in pairs]
    assert setup_context_source.id not in source_ids
