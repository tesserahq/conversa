"""CloudEvents payloads for channel installation lifecycle."""

from __future__ import annotations

from app.models.channel_installation import ChannelInstallation
from tessera_sdk.infra.events.event import Event, event_source, event_type  # type: ignore[import-untyped]

CHANNEL_INSTALLATION_CREATED = "channel_installation.created"


def build_channel_installation_created_event(
    installation: ChannelInstallation,
) -> Event:
    """Build a CloudEvent for a new channel workspace installation."""
    event_data: dict[str, object] = {
        "channel": installation.channel,
        "account_id": installation.account_id,
        "account_name": installation.account_name or "",
    }
    return Event(
        source=event_source(),
        event_type=event_type(CHANNEL_INSTALLATION_CREATED),
        event_data=event_data,
        subject=f"/channel-installations/{installation.id}",
        user_id=str(installation.created_by_id) if installation.created_by_id else "",
        labels={"channel": installation.channel, "account_id": installation.account_id},
        tags=[
            f"channel:{installation.channel}",
            f"account_id:{installation.account_id}",
        ],
    )
