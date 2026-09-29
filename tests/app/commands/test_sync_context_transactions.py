"""Context sync checkpoints each source's sync state as soon as that source
is done, so a failing source cannot undo the ones before it."""

from unittest.mock import Mock

import pytest

from app.adapters.context_pack_fetcher import ContextPackFetcher, FetchResult
from app.commands.sync_context_for_user_command import SyncContextForUserCommand
from app.models.context_source import ContextSource, ContextSourceState


@pytest.fixture
def two_sources(db, faker, setup_context_source):
    other = ContextSource(
        source_id=f"test-{faker.lexify('??????').lower()}",
        display_name=faker.company(),
        base_url="https://api.example.com",
        credential_id=None,
        capabilities={"supports_etag": True, "supports_since_cursor": False},
        poll_interval_seconds=3600,
        enabled=True,
    )
    db.add(other)
    db.flush()
    return setup_context_source, other


def test_source_state_survives_a_later_source_failure(
    db, execution_boundary, two_sources, setup_user, monkeypatch
):
    outcomes = iter([FetchResult(error="HTTP 401"), RuntimeError("source unavailable")])

    def fetch(self, user_id, source, state):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(ContextPackFetcher, "fetch", fetch)
    monkeypatch.setattr(
        SyncContextForUserCommand,
        "_get_enabled_sources",
        Mock(return_value=list(two_sources)),
    )

    with pytest.raises(RuntimeError, match="source unavailable"):
        with execution_boundary():
            SyncContextForUserCommand(db).execute(setup_user.id)

    db.expire_all()
    states = (
        db.query(ContextSourceState)
        .filter(ContextSourceState.user_id == setup_user.id)
        .all()
    )
    assert len(states) == 2
    assert sorted(s.last_error or "" for s in states) == ["", "HTTP 401"]
