"""Repository for ChannelInstallation — manages per-workspace OAuth installations."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.credentials import decrypt_credential_fields, encrypt_credential_fields
from app.models.channel_installation import ChannelInstallation
from app.repositories.soft_delete_repository import SoftDeleteRepository


class ChannelInstallationRepository(SoftDeleteRepository[ChannelInstallation]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, ChannelInstallation)

    def get_by_channel_and_account(
        self, channel: str, account_id: str
    ) -> Optional[ChannelInstallation]:
        return (
            self.db.query(ChannelInstallation)
            .filter(
                ChannelInstallation.channel == channel,
                ChannelInstallation.account_id == account_id,
            )
            .first()
        )

    def upsert(
        self,
        channel: str,
        account_id: str,
        sensitive_data: Dict[str, Any],
        *,
        account_name: Optional[str] = None,
        bot_user_id: Optional[str] = None,
        installer_user_id: Optional[str] = None,
        scopes: Optional[str] = None,
        created_by_id: Optional[UUID] = None,
    ) -> ChannelInstallation:
        """Create or update a channel installation, encrypting sensitive_data."""
        encrypted = encrypt_credential_fields(sensitive_data)
        installation = self.get_by_channel_and_account(channel, account_id)

        if installation:
            installation.encrypted_data = encrypted  # type: ignore[assignment]
            if account_name is not None:
                installation.account_name = account_name  # type: ignore[assignment]
            if bot_user_id is not None:
                installation.bot_user_id = bot_user_id  # type: ignore[assignment]
            if installer_user_id is not None:
                installation.installer_user_id = installer_user_id  # type: ignore[assignment]
            if scopes is not None:
                installation.scopes = scopes  # type: ignore[assignment]
        else:
            installation = ChannelInstallation(
                channel=channel,
                account_id=account_id,
                account_name=account_name,
                bot_user_id=bot_user_id,
                installer_user_id=installer_user_id,
                scopes=scopes,
                encrypted_data=encrypted,
                created_by_id=created_by_id,
            )
            self.db.add(installation)

        self.db.commit()
        self.db.refresh(installation)
        return installation

    def get_sensitive_data(self, installation: ChannelInstallation) -> Dict[str, Any]:
        """Decrypt and return the sensitive fields for an installation."""
        return decrypt_credential_fields(bytes(installation.encrypted_data))
