"""Telegram channel plugin using python-telegram-bot (v22)."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any, Optional

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from app.channels.base import ChannelCapabilities, ChannelMeta
from app.channels.envelope import InboundMessage, OutboundMessage
from app.core.app_state import state
from app.db import SessionLocal
from app.infra.logging_config import get_logger
from app.services.session_manager import SessionManager
from app.utils.db.db_session_helper import db_session
from .config import TelegramConfig

logger = get_logger()


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
        self._app = ApplicationBuilder().token(self.cfg.bot_token).build()
        self._app.add_handler(MessageHandler(filters.ALL, self._on_update))
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

    
        linked_user = state.router._linker.get_linked_user(
            inbound.channel, inbound.sender_id
        )
        user_id = linked_user.id if linked_user else None
        
        reply = await state.router.route_to_llm(
            inbound, user_id=user_id
        )

        await self.send(reply)

    async def handle_inbound(self, msg: InboundMessage) -> None:
         
        try:
            linked_user = state.router._linker.get_linked_user(
                msg.channel, msg.sender_id
            )
            user_id = linked_user.id if linked_user else None 
            reply = await state.router.route_to_llm(
                msg, user_id=user_id
            )
        finally:
            db.close()
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
