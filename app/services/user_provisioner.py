"""The local `users` projection of Identies users, and the one place that registers them."""

from contextlib import AbstractContextManager
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import session_scope as default_session_scope
from app.repositories.user_repository import UserRepository
from app.schemas.identies_user import IdentiesUser
from app.schemas.user import User
from app.services.identies_directory import IdentiesApiDirectory, IdentiesDirectory

SessionScope = Callable[[], AbstractContextManager[Session]]


class UnknownUserError(Exception):
    """The user is not registered in Conversa and Identies does not know it either."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"User {user_id} is not registered")
        self.user_id = user_id


class UserProvisioner:
    """Keeps local user rows in step with Identies.

    Every path that needs a local user goes through here: the linked-account
    flow, the chat API's existence check, and the user.* event listener.
    Identies is called outside any database transaction, and results are
    returned as schemas, so no caller touches an ORM row after its session ends.
    """

    def __init__(
        self,
        directory: IdentiesDirectory | None = None,
        session_scope: SessionScope = default_session_scope,
    ) -> None:
        self._directory = directory or IdentiesApiDirectory()
        self._session_scope = session_scope

    def ensure_user(self, user_id: UUID) -> User | None:
        """Return the local user, registering it from Identies when it is missing.

        Returns None when Identies does not know the user, or when the local row
        was soft-deleted. A tombstone is never revived by a read.
        """
        with self._session_scope() as db:
            existing = UserRepository(db).get_user_any_status(user_id)
            if existing is not None:
                return None if existing.deleted_at else User.model_validate(existing)

        identies_user = self._directory.get_user(user_id)
        if identies_user is None:
            return None
        return self.sync(identies_user)

    def sync(self, identies_user: IdentiesUser) -> User:
        """Create or refresh the local row from an Identies user."""
        with self._session_scope() as db:
            user = UserRepository(db).upsert_user(identies_user.to_onboard())
            return User.model_validate(user)
