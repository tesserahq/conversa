"""Beat's due-pairs task enqueues one sync per due user. It reads the user ids
inside the managed session, because the session's commit expires the loaded
users and closing it detaches them."""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import sessionmaker

from app.tasks import context_sync_task


@pytest.fixture
def run_as_entry_point(db, monkeypatch):
    # Mirror app.db.session_scope: a new session that commits on success and
    # closes on exit. Closing detaches the rows loaded inside it.
    @contextmanager
    def session_scope():
        session = sessionmaker(
            bind=db.get_bind(), join_transaction_mode="create_savepoint"
        )()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(context_sync_task, "session_scope", session_scope)


def test_sync_all_due_enqueues_each_due_user(
    db, setup_context_source, setup_user, run_as_entry_point, monkeypatch
):
    enqueue = Mock()
    monkeypatch.setattr(context_sync_task.sync_context_for_user_task, "delay", enqueue)

    count = context_sync_task.sync_context_all_due_task()

    enqueue.assert_any_call(str(setup_user.id))
    assert count >= 1
    assert count == enqueue.call_count
