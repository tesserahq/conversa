"""Names of the events Identies publishes, namespaced by its EVENT_TYPE_PREFIX."""

from app.config import get_settings


class IdentiesEventNames:
    """The NATS subscription and event types for one Identies event prefix."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    @property
    def subscription(self) -> str:
        """Subject pattern that matches every Identies event."""
        return f"{self._prefix}.>"

    @property
    def external_account_linked(self) -> str:
        return self._event_type("external_account.linked")

    @property
    def user_created(self) -> str:
        return self._event_type("user.created")

    @property
    def user_updated(self) -> str:
        return self._event_type("user.updated")

    def _event_type(self, name: str) -> str:
        return f"{self._prefix}.{name}"


def identies_event_names() -> IdentiesEventNames:
    """Event names for the prefix configured for this deployment."""
    return IdentiesEventNames(get_settings().identies_event_prefix)
