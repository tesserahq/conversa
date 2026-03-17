"""Slack channel plugin using slack-bolt with Socket Mode (DMs only)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient

from app.channels.base import ChannelCapabilities, ChannelMeta
from app.channels.envelope import InboundMessage, OutboundMessage
from app.channels.plugins.slack.installation_store import SlackInstallationStore
from app.core.app_state import state
from app.infra.logging_config import get_logger
from .config import SlackConfig

logger = get_logger()


class SlackPlugin:
    id = "slack"
    meta = ChannelMeta(label="Slack", docs="/channels/slack")
    capabilities = ChannelCapabilities(
        chat_types=["direct"],
        supports_webhook=False,
        supports_polling=False,
        supports_media=False,
        supports_reactions=False,
    )

    def __init__(self, cfg: SlackConfig) -> None:
        self.cfg = cfg
        self._installation_store = SlackInstallationStore()
        self._bolt_app = AsyncApp(
            signing_secret=cfg.signing_secret,
            installation_store=self._installation_store,
            oauth_settings=None,
        )
        self._socket_handler: Optional[AsyncSocketModeHandler] = None
        self._socket_task: Optional[asyncio.Task[None]] = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._bolt_app.event("message")
        async def on_message(event: dict[str, Any], say: Any) -> None:
            # Only handle DMs; skip bot messages and message edits
            if event.get("channel_type") != "im":
                return
            if event.get("bot_id") or event.get("subtype"):
                return
            await self._handle_dm(event)

        @self._bolt_app.event("app_mention")
        async def on_app_mention(event: dict[str, Any], say: Any) -> None:
            await self._handle_dm(event)

    async def _handle_dm(self, event: dict[str, Any]) -> None:
        team_id = event.get("team") or ""
        sender_id = event.get("user") or "unknown"
        chat_id = event.get("channel") or ""
        message_id = event.get("ts") or ""
        thread_ts = event.get("thread_ts")
        text = event.get("text") or ""
        ts_float = (
            float(message_id) if message_id else datetime.now(timezone.utc).timestamp()
        )

        logger.info("Slack DM from %s in %s: %s", sender_id, chat_id, text)

        inbound = InboundMessage(
            channel="slack",
            account_id=team_id,
            sender_id=sender_id,
            chat_id=chat_id,
            thread_id=thread_ts,
            message_id=message_id,
            text=text,
            media=[],
            timestamp=datetime.fromtimestamp(ts_float, tz=timezone.utc),
            raw=event,
        )

        linked_user = state.router._linker.get_linked_user(
            inbound.channel, inbound.sender_id
        )
        user_id = linked_user.id if linked_user else None

        reply = await state.router.route_to_llm(inbound, user_id=user_id)
        await self.send(reply)

    async def start(self) -> None:
        self._socket_handler = AsyncSocketModeHandler(
            self._bolt_app, self.cfg.app_token
        )
        self._socket_task = asyncio.create_task(self._run_socket())

    async def _run_socket(self) -> None:
        assert self._socket_handler is not None
        await self._socket_handler.start_async()

    async def stop(self) -> None:
        if self._socket_handler is not None:
            await self._socket_handler.close_async()
        if self._socket_task is not None:
            self._socket_task.cancel()

    async def handle_inbound(self, msg: InboundMessage) -> None:
        linked_user = state.router._linker.get_linked_user(msg.channel, msg.sender_id)
        user_id = linked_user.id if linked_user else None
        reply = await state.router.route_to_llm(msg, user_id=user_id)
        await self.send(reply)

    async def send(self, msg: OutboundMessage) -> None:
        if not msg.text:
            return

        installation = await self._installation_store.async_find_installation(
            enterprise_id=None,
            team_id=msg.account_id,
        )
        if not installation or not installation.bot_token:
            logger.error("No Slack installation found for team %s", msg.account_id)
            return

        client = AsyncWebClient(token=installation.bot_token)
        kwargs: dict[str, Any] = {
            "channel": msg.chat_id,
            "text": msg.text,
        }
        if msg.thread_id:
            kwargs["thread_ts"] = msg.thread_id
        elif msg.reply_to:
            kwargs["thread_ts"] = msg.reply_to

        await client.chat_postMessage(**kwargs)
