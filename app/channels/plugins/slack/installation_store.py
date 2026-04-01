"""Bolt AsyncInstallationStore backed by ChannelInstallationRepository."""

from __future__ import annotations

from logging import getLogger
from typing import Optional

from slack_sdk.oauth.installation_store import Installation
from slack_sdk.oauth.installation_store.async_installation_store import (
    AsyncInstallationStore,
)

from app.repositories.channel_installation_repository import (
    ChannelInstallationRepository,
)
from app.utils.db.db_session_helper import db_session

logger = getLogger(__name__)

CHANNEL = "slack"


class SlackInstallationStore(AsyncInstallationStore):
    async def async_save(self, installation: Installation) -> None:
        team_id = installation.team_id or ""
        sensitive = {"bot_token": installation.bot_token}
        with db_session() as db:
            repo = ChannelInstallationRepository(db)
            repo.upsert(
                channel=CHANNEL,
                account_id=team_id,
                sensitive_data=sensitive,
                account_name=installation.team_name,
                bot_user_id=installation.bot_user_id,
                installer_user_id=installation.installer_user_id,
                scopes=",".join(installation.bot_scopes or []),
            )
        logger.info("Saved Slack installation for team %s", team_id)

    async def async_find_installation(
        self,
        *,
        enterprise_id: Optional[str],
        team_id: Optional[str],
        user_id: Optional[str] = None,
        is_enterprise_install: Optional[bool] = False,
    ) -> Optional[Installation]:
        lookup_id = team_id or enterprise_id or ""
        with db_session() as db:
            repo = ChannelInstallationRepository(db)
            record = repo.get_by_channel_and_account(CHANNEL, lookup_id)
            if not record:
                return None
            data = repo.get_sensitive_data(record)

            team_id = str(record.account_id)
            team_name = str(record.account_name) if record.account_name else None
            bot_user_id = str(record.bot_user_id) if record.bot_user_id else None
            scopes = str(record.scopes).split(",") if record.scopes else []

        return Installation(
            user_id=user_id,
            team_id=team_id,
            team_name=team_name,
            bot_token=data.get("bot_token"),
            bot_user_id=bot_user_id,
            bot_scopes=scopes,
        )
