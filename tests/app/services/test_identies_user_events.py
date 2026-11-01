"""IdentiesUserEventHandler registers humans from user.* events and starts their first sync."""

from uuid import uuid4

import pytest
from tessera_sdk.infra.events import Event

from app.core.identies_events import IdentiesEventNames
from app.services.identies_user_events import IdentiesUserEventHandler

EVENT_NAMES = IdentiesEventNames("com.identies")
USER_CREATED_EVENT_TYPE = EVENT_NAMES.user_created
USER_UPDATED_EVENT_TYPE = EVENT_NAMES.user_updated


class _RecordingUsers:
    def __init__(self) -> None:
        self.synced: list = []

    def sync(self, identies_user):
        self.synced.append(identies_user)


def _event(event_type: str, **user_fields) -> Event:
    user = {
        "id": str(uuid4()),
        "external_id": "auth0|abc",
        "email": "new.user@example.com",
        "first_name": "New",
        "last_name": "User",
        "kind": "human",
        "service_account": False,
    }
    user.update(user_fields)
    return Event(
        source="identies",
        event_type=event_type,
        event_data={"user": user},
    )


@pytest.fixture
def users():
    return _RecordingUsers()


@pytest.fixture
def enqueued():
    return []


@pytest.fixture
def handler(users, enqueued):
    return IdentiesUserEventHandler(
        users=users, enqueue_sync=enqueued.append, event_names=EVENT_NAMES
    )


def test_created_human_is_registered_and_its_first_sync_is_queued(
    handler, users, enqueued
):
    event = _event(USER_CREATED_EVENT_TYPE)

    handler.handle(event)

    user_id = event.event_data["user"]["id"]
    assert [str(u.id) for u in users.synced] == [user_id]
    assert enqueued == [user_id]


def test_updated_human_is_refreshed_without_queuing_a_sync(handler, users, enqueued):
    handler.handle(_event(USER_UPDATED_EVENT_TYPE, first_name="Renamed"))

    assert [u.first_name for u in users.synced] == ["Renamed"]
    assert enqueued == []


@pytest.mark.parametrize(
    "user_fields",
    [
        {"kind": "agent", "service_account": True},
        {"kind": "service_account", "service_account": True},
    ],
)
def test_agents_and_service_accounts_are_skipped(handler, users, enqueued, user_fields):
    handler.handle(_event(USER_CREATED_EVENT_TYPE, **user_fields))

    assert users.synced == []
    assert enqueued == []


def test_missing_kind_is_treated_as_human(handler, users, enqueued):
    event = _event(USER_CREATED_EVENT_TYPE)
    del event.event_data["user"]["kind"]
    del event.event_data["user"]["service_account"]

    handler.handle(event)

    assert len(users.synced) == 1
    assert len(enqueued) == 1


@pytest.mark.parametrize(
    "event_type,expected",
    [
        (USER_CREATED_EVENT_TYPE, True),
        (USER_UPDATED_EVENT_TYPE, True),
        ("com.identies.user.deleted", False),
        ("com.identies.external_account.linked", False),
    ],
)
def test_handles_only_the_user_registration_events(handler, event_type, expected):
    assert handler.handles(event_type) is expected
