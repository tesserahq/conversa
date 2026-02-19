from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.channels.envelope import InboundMessage, OutboundMessage
from app.core.linker import Linker
from app.services.session_manager import SessionManager
from app.workers.llm import LLMRunner, build_llm_runner_from_env
from app.utils.db.db_session_helper import db_session

LINK_URL = "https://app.mylinden.family/link/{link_token}"

WELCOME_MESSAGE = "Hello and welcome. Please click the link below to connect your {channel} account to your Linden account so we can continue. This link is valid for 10 minutes: {link_url}"


class Router:
    """Deterministic routing: replies go back to the same channel/chat/thread."""

    def __init__(self, llm: LLMRunner | None = None) -> None:
        self._llm = llm or build_llm_runner_from_env()
        self._linker = Linker()

    async def route_to_llm(
        self,
        msg: InboundMessage,
        user_id: Optional[UUID] = None,
    ) -> OutboundMessage:
        if self.is_linked(msg.channel, msg.sender_id) is False:
            return self._create_link_outbound_message(msg)

        with db_session() as db:
            session_manager = SessionManager(db)
            session = session_manager.get_or_create_session(msg, user_id)
            history = session_manager.get_history_for_llm(session.id, limit=50)
            reply_text = await self._llm.run(msg, history=history)
            outbound = OutboundMessage(
                channel=msg.channel,
                account_id=msg.account_id,
                chat_id=msg.chat_id,
                thread_id=msg.thread_id,
                text=reply_text,
                reply_to=msg.message_id,
                media=[],
            )
            session_manager.add_turn(session.id, msg, outbound)
        return outbound

    def _create_link_outbound_message(self, msg: InboundMessage) -> OutboundMessage:
        link_token = self._linker.generate_link_token(msg.channel, msg.sender_id)
        link_url = LINK_URL.format(link_token=link_token)
        welcome_message = WELCOME_MESSAGE.format(channel=msg.channel, link_url=link_url)
        return OutboundMessage(
            channel=msg.channel,
            account_id=msg.account_id,
            chat_id=msg.chat_id,
            thread_id=msg.thread_id,
            text=welcome_message,
            reply_to=msg.message_id,
            media=[],
        )

    def is_linked(self, channel: str, external_id: str) -> bool:
        return self._linker.is_account_linked(channel, external_id)
