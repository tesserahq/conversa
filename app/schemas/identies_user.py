"""A user as Identies describes it, whether it arrives from the Identies API or in a user.* event."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.user import UserOnboard

HUMAN_KIND = "human"


class IdentiesUser(BaseModel):
    """Identies' view of a user, as a local projection needs it.

    The Identies API returns ``service_account`` but no ``kind``; user.* events
    carry both. A missing ``kind`` means human, as docs/user_events.md requires.
    """

    model_config = ConfigDict(extra="ignore")

    id: UUID
    external_id: str | None = None
    email: EmailStr | None = None
    first_name: str = ""
    last_name: str = ""
    preferred_name: str | None = None
    avatar_url: str | None = None
    provider: str | None = None
    verified: bool = False
    verified_at: datetime | None = None
    confirmed_at: datetime | None = None
    kind: str = HUMAN_KIND
    service_account: bool | None = None

    @property
    def is_human(self) -> bool:
        return self.kind == HUMAN_KIND and not self.service_account

    def to_onboard(self) -> UserOnboard:
        """The local-row input for this user. Only the fields a local row stores are kept."""
        fields = self.model_dump(include=set(UserOnboard.model_fields))
        fields["service_account"] = not self.is_human
        return UserOnboard(**fields)
