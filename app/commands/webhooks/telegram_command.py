"""
Command to handle Telegram webhook updates.

Receives raw webhook data, validates secret, parses update, persists inbound event.
Handles /start bot command by creating a link token via Identies and sending it to the user.
"""

from __future__ import annotations

import html
import logging
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from tessera_sdk.identies import IdentiesClient
from tessera_sdk.utils.m2m_token import M2MTokenClient

from app.adapters.telegram import TelegramAdapter
from app.commands.base_telegram import BaseTelegramCommand
from app.commands.outbound.send_outbound_command import SendOutboundCommand
from app.config import get_settings
from app.schemas.conversa import Channel, OutboundMessage
from app.schemas.telegram import TelegramWebhookUpdate
from app.services.conversation_event_service import ConversationEventService

START_COMMAND = "/start"
BOT_ENTITY_TYPE = "bot_command"


class TelegramWebhookCommand(BaseTelegramCommand):
    """
    Command to handle Telegram webhook updates.
    Validates X-Telegram-Bot-Api-Secret-Token, parses update, persists inbound event.
    On /start bot command, creates a link token via Identies and sends it to the user.
    """

    def __init__(self, db: Session, nats_publisher: Optional[object] = None) -> None:
        self.db = db
        self.settings = get_settings()
        self._adapter = self.get_telegram_adapter()
        self.conversation_event_service = ConversationEventService(db)
        self.nats_publisher = nats_publisher
        self.logger = logging.getLogger(__name__)

    async def execute(
        self, request: Request, body: TelegramWebhookUpdate
    ) -> dict[str, str]:
        """
        Execute the Telegram webhook: validate secret, parse body, persist event.

        Args:
            request: The incoming webhook request (headers for secret validation).
            body: Validated Telegram webhook update payload.

        Returns:
            dict: {"status": "ok"} on success.

        Raises:
            HTTPException: 503 if Telegram not configured, 403 on invalid secret,
                400 on invalid Telegram update.
        """
        if self._adapter is None:
            raise HTTPException(
                status_code=503,
                detail="Telegram integration is not configured or disabled",
            )
        headers = dict(request.headers) if request.headers else {}
        if not self._adapter.verify_webhook(
            self.settings.telegram_webhook_secret, headers
        ):
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
        try:
            inbound = self._adapter.parse_webhook(body.model_dump(by_alias=True))
        except (ValueError, KeyError, TypeError) as e:
            self.logger.warning("Telegram webhook parse error: %s", e)
            raise HTTPException(
                status_code=400, detail="Invalid Telegram update"
            ) from e
        self.conversation_event_service.create_event_from_inbound(inbound)

        self.logger.info("Telegram webhook received: %s", inbound)

        # On /start bot command: create link token via Identies and send to user
        start_result = self._is_start_command(body)
        if start_result:
            chat_id, external_user_id = start_result
            await self._send_link_token_for_start(chat_id, external_user_id)

        return {"status": "ok"}

    def _get_m2m_token(self) -> str:
        """Get an M2M token for calling Identies."""
        return M2MTokenClient().get_token_sync().access_token

    def _is_start_command(
        self, body: TelegramWebhookUpdate
    ) -> Optional[tuple[str, str]]:
        """
        Detect if the webhook payload is a /start bot command.

        Returns:
            (chat_id, external_user_id) if message is a /start command, None otherwise.
        """
        message = body.message
        if message is None:
            return None
        if message.text != START_COMMAND:
            return None
        entities = message.entities or []
        if not any(e.type == BOT_ENTITY_TYPE for e in entities):
            return None
        return (str(message.chat.id), str(message.from_.id))

    async def _send_link_token_for_start(
        self, chat_id: str, external_user_id: str
    ) -> None:
        """
        Create a link token via Identies and send it to the user over Telegram.
        Logs and swallows errors so the webhook still returns 200.
        """
        try:
            m2m_token = self._get_m2m_token()
            identies_client = IdentiesClient(api_token=m2m_token)
            link_response = identies_client.create_link_token(
                platform="telegram",
                external_user_id=external_user_id,
            )
            link_url = f"https://app.mylinden.family/link/{link_response.token}"
            link_url_escaped = html.escape(link_url, quote=True)
            outbound_body = OutboundMessage(
                channel=Channel.TELEGRAM,
                external_user_id=chat_id,
                text=(
                    f'Your link token: <a href="{link_url_escaped}">Link your account</a>. '
                    "Use it in the app to link your Telegram account."
                ),
                parse_mode="HTML",
            )
            send_outbound = SendOutboundCommand(self.db)
            await send_outbound.execute(outbound_body)
        except Exception as e:
            self.logger.exception(
                "Failed to create or send link token for /start: %s", e
            )
