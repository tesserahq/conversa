"""Telegram channel plugin using python-telegram-bot (v22)."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any, Optional

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from tessera_sdk.clients._base.exceptions import TesseraError

from app.channels.base import ChannelCapabilities, ChannelMeta
from app.channels.envelope import InboundMessage, OutboundMessage
from app.core.app_state import state
from app.infra.logging_config import get_logger
from .config import TelegramConfig
from telegram.request import HTTPXRequest

logger = get_logger()
LINKED_USER_RESOLUTION_ERROR = "Sorry, we couldn't verify your linked account right now. Please try again in a moment."


class TelegramPlugin:
    id = "telegram"
    meta = ChannelMeta(label="Telegram", docs="/channels/telegram")
    capabilities = ChannelCapabilities(
        chat_types=["direct", "group", "channel", "thread"],
        supports_webhook=True,
        supports_polling=True,
        supports_media=True,
        supports_reactions=False,
    )

    def __init__(self, cfg: TelegramConfig) -> None:
        self.cfg = cfg
        self._app: Optional[ApplicationBuilder] = None
        self._polling_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30,
            read_timeout=60,
            write_timeout=30,
            pool_timeout=30,
        )
        self._app = (
            ApplicationBuilder().token(self.cfg.bot_token).request(request).build()
        )
        self._app.add_handler(MessageHandler(filters.ALL, self._on_update))
        self._app.add_error_handler(self._on_error)
        await self._app.initialize()

        if self.cfg.mode == "polling":
            self._polling_task = asyncio.create_task(self._run_polling())

    async def stop(self) -> None:
        if self._app is None:
            return
        if self._polling_task is not None:
            try:
                await self._app.updater.stop()
            except RuntimeError:
                pass
            self._polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._polling_task
        await self._app.shutdown()

    async def _run_polling(self) -> None:
        assert self._app is not None
        await self._app.start()
        await self._app.updater.start_polling()

    async def _on_update(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        msg = update.effective_message
        if msg is None:
            return

        sender = msg.from_user.id if msg.from_user else "unknown"
        chat_id = str(msg.chat_id)
        message_id = str(msg.message_id)
        text = msg.text or msg.caption
        ts = datetime.fromtimestamp(msg.date.timestamp(), tz=timezone.utc)

        logger.info(f"Received message from {sender} in chat {chat_id}: {text}")

        inbound = InboundMessage(
            channel="telegram",
            account_id=self.cfg.account_id,
            sender_id=str(sender),
            chat_id=chat_id,
            thread_id=str(msg.message_thread_id) if msg.message_thread_id else None,
            message_id=message_id,
            text=text,
            media=[],
            timestamp=ts,
            raw=update.to_dict(),
        )

        linked_user = state.router._linker.get_or_resolve_linked_user(
            inbound.channel, inbound.sender_id
        )
        if linked_user is None:
            logger.warning(
                "Linked user missing in cache for %s sender %s",
                inbound.channel,
                inbound.sender_id,
            )
            await self.send(
                OutboundMessage(
                    channel=inbound.channel,
                    account_id=inbound.account_id,
                    chat_id=inbound.chat_id,
                    thread_id=inbound.thread_id,
                    text=LINKED_USER_RESOLUTION_ERROR,
                    reply_to=inbound.message_id,
                    media=[],
                )
            )
            return
        user_id = linked_user.id

        reply = await state.router.route_to_llm(inbound, user_id=user_id)

        await self.send(reply)

    async def _on_error(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        logger.error("Unhandled exception in Telegram update", exc_info=context.error)
        if not isinstance(update, Update):
            return
        msg = update.effective_message
        if msg is None:
            return
        if isinstance(context.error, TesseraError):
            text = "Sorry, I'm having trouble reaching an internal service. Please try again in a moment."
        else:
            text = "Something went wrong. Please try again."
        with contextlib.suppress(Exception):
            await msg.reply_text(text)

    async def handle_inbound(self, msg: InboundMessage) -> None:

        linked_user = state.router._linker.get_linked_user(msg.channel, msg.sender_id)
        if linked_user is None:
            logger.warning(
                "Linked user missing in cache for %s sender %s",
                msg.channel,
                msg.sender_id,
            )
            await self.send(
                OutboundMessage(
                    channel=msg.channel,
                    account_id=msg.account_id,
                    chat_id=msg.chat_id,
                    thread_id=msg.thread_id,
                    text=LINKED_USER_RESOLUTION_ERROR,
                    reply_to=msg.message_id,
                    media=[],
                )
            )
            return
        user_id = linked_user.id
        reply = await state.router.route_to_llm(msg, user_id=user_id)

        await self.send(reply)

    async def send(self, msg: OutboundMessage) -> None:
        if self._app is None:
            raise RuntimeError("Telegram plugin not started")
        if not msg.text:
            return
        await self._app.bot.send_message(
            chat_id=int(msg.chat_id),
            text=msg.text,
            reply_to_message_id=int(msg.reply_to) if msg.reply_to else None,
        )

    async def process_webhook_update(self, payload: dict[str, Any]) -> None:
        if self._app is None:
            raise RuntimeError("Telegram plugin not started")
        update = Update.de_json(payload, self._app.bot)
        await self._app.process_update(update)
