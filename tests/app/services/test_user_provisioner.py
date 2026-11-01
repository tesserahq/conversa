"""UserProvisioner keeps local user rows in step with Identies, without duplicate rows."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.user import User as UserModel
from app.schemas.identies_user import IdentiesUser
from app.services.user_provisioner import UserProvisioner


class _FakeDirectory:
    def __init__(self, users: dict | None = None) -> None:
        self._users = users or {}
        self.lookups: list = []

    def get_user(self, user_id):
        self.lookups.append(user_id)
        return self._users.get(user_id)


def _identies_user(**overrides) -> IdentiesUser:
    fields = {
        "id": uuid4(),
        "external_id": f"auth0|{uuid4().hex}",
        "email": "new.user@example.com",
        "first_name": "New",
        "last_name": "User",
    }
    fields.update(overrides)
    return IdentiesUser(**fields)


def test_ensure_user_returns_existing_user_without_asking_identies(
    db, execution_boundary, setup_user
):
    directory = _FakeDirectory()
    users = UserProvisioner(directory=directory, session_scope=execution_boundary)

    user = users.ensure_user(setup_user.id)

    assert user.id == setup_user.id
    assert directory.lookups == []


def test_ensure_user_registers_missing_user_from_identies_once(db, execution_boundary):
    identies_user = _identies_user()
    directory = _FakeDirectory({identies_user.id: identies_user})
    users = UserProvisioner(directory=directory, session_scope=execution_boundary)

    first = users.ensure_user(identies_user.id)
    second = users.ensure_user(identies_user.id)

    assert first.id == identies_user.id
    assert first.email == "new.user@example.com"
    assert second.id == identies_user.id
    assert directory.lookups == [identies_user.id]
    assert db.query(UserModel).filter(UserModel.id == identies_user.id).count() == 1


def test_ensure_user_returns_none_when_identies_does_not_know_the_user(
    db, execution_boundary
):
    unknown_id = uuid4()
    users = UserProvisioner(
        directory=_FakeDirectory(), session_scope=execution_boundary
    )

    assert users.ensure_user(unknown_id) is None
    assert db.query(UserModel).filter(UserModel.id == unknown_id).count() == 0


def test_ensure_user_does_not_revive_a_soft_deleted_user(
    db, execution_boundary, setup_user
):
    setup_user.deleted_at = datetime.now(UTC)
    db.flush()
    directory = _FakeDirectory({setup_user.id: _identies_user(id=setup_user.id)})
    users = UserProvisioner(directory=directory, session_scope=execution_boundary)

    assert users.ensure_user(setup_user.id) is None
    assert directory.lookups == []


def test_sync_refreshes_the_existing_row_instead_of_duplicating_it(
    db, execution_boundary, setup_user
):
    users = UserProvisioner(
        directory=_FakeDirectory(), session_scope=execution_boundary
    )
    renamed = _identies_user(id=setup_user.id, first_name="Renamed")

    users.sync(renamed)
    synced = users.sync(renamed)

    assert synced.first_name == "Renamed"
    assert db.query(UserModel).filter(UserModel.id == setup_user.id).count() == 1


def test_sync_flags_agents_as_service_accounts_in_the_row(db, execution_boundary):
    users = UserProvisioner(
        directory=_FakeDirectory(), session_scope=execution_boundary
    )
    agent = _identies_user(kind="agent")

    users.sync(agent)

    stored = db.query(UserModel).filter(UserModel.id == agent.id).one()
    assert stored.service_account is True
