from __future__ import annotations

from app.channels.envelope import InboundMessage, OutboundMessage
from app.workers.llm import LLMRunner, build_llm_runner_from_env
from app.core.linker import Linker

LINK_URL = "https://app.mylinden.family/link/{link_token}"

WELCOME_MESSAGE = "Hello and welcome. Please click the link below to connect your {channel} account to your Linden account so we can continue. This link is valid for 10 minutes: {link_url}"


class Router:
    """Deterministic routing: replies go back to the same channel/chat/thread."""

    def __init__(self, llm: LLMRunner | None = None) -> None:
        self._llm = llm or build_llm_runner_from_env()
        self._linker = Linker()

    async def route_to_llm(self, msg: InboundMessage) -> OutboundMessage:
        if self.is_linked(msg.channel, msg.sender_id) is False:
            return self._create_link_outbound_message(msg)

        reply_text = await self._llm.run(msg)
        return OutboundMessage(
            channel=msg.channel,
            account_id=msg.account_id,
            chat_id=msg.chat_id,
            thread_id=msg.thread_id,
            text=reply_text,
            reply_to=msg.message_id,
            media=[],
        )

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
