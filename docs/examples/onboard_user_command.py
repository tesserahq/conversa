import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.schemas.user import UserOnboard
from app.services.user_service import UserService
from app.models.user import User
from app.events.user_events import build_user_created_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class OnboardUserCommand:
    """
    Command to onboard a new user.
    """

    def __init__(
        self, db: Session, nats_publisher: Optional[NatsEventPublisher] = None
    ):
        self.db = db
        self.user_service = UserService(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(self, user_onboard: UserOnboard) -> User:
        """
        Execute the command to onboard a user.

        Args:
            user_onboard: The user onboarding data

        Returns:
            User: The onboarded user

        Raises:
            Exception: If user onboarding fails
        """
        try:
            # Onboard the user
            user = self.user_service.onboard_user(user_onboard)

            if not user:
                raise Exception("Failed to onboard user")

            self._publish_user_created_event(user)

            return user

        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to onboard user: {str(e)}")

    def _publish_user_created_event(self, user: User) -> None:
        """
        Publish a user created event.

        Args:
            user: The onboarded user
        """
        event = build_user_created_event(user)

        if self.nats_publisher is not None:
            self.logger.info(
                f"Publishing user-created event to NATS: {event.event_type}"
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception("Failed to publish user-created event to NATS")
