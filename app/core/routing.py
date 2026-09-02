from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from app.channels.envelope import InboundMessage, OutboundMessage
from app.config import get_settings
from app.infra.logging_config import get_logger
from app.core.linker import Linker
from app.repositories.context_snapshot_repository import ContextSnapshotRepository
from app.repositories.session_manager import SessionManager
from app.repositories.session_repository import SessionRepository
from app.tasks.context_sync_task import sync_context_for_user_task
from app.utils.db.db_session_helper import db_session
from app.workers.llm import LLMRunner, build_llm_runner_from_env
import asyncio

logger = get_logger("routing")

WELCOME_MESSAGE = "Hello and welcome. Please click the link below to connect your {channel} account to your Linden account so we can continue. This link is valid for 10 minutes: {link_url}"
LINK_RESOLUTION_ERROR_MESSAGE = "Sorry, we couldn't verify your linked account right now. Please try again in a moment."

# Sessions created by the direct chat API (as opposed to a channel webhook)
# use this synthetic channel value. There is no external chat platform
# involved, so chat_id is generated rather than derived from a webhook payload.
API_CHANNEL = "api"


class Router:
    """Deterministic routing: replies go back to the same channel/chat/thread."""

    def __init__(self, llm: LLMRunner | None = None) -> None:
        self._llm = llm or build_llm_runner_from_env()
        self._linker = Linker()

    async def route_to_llm(
        self,
        msg: InboundMessage,
        user_id: Optional[UUID],
    ) -> OutboundMessage:
        linked_user = await asyncio.to_thread(
            self._linker.get_or_resolve_linked_user, msg.channel, msg.sender_id
        )
        if linked_user is None:
            return self._create_link_outbound_message(msg)
        resolved_user_id = user_id or linked_user.id
        if resolved_user_id is None:
            return self._create_link_resolution_error_outbound_message(msg)

        with db_session() as db:
            session_manager = SessionManager(db)
            session = session_manager.get_or_create_session(msg, resolved_user_id)
            session_id = session.id
            history = session_manager.get_history_for_llm(session_id, limit=50)
            context = self._load_context_for_user(db, session.user_id)
            logger.info(
                "Prepared LLM input for session=%s user_id=%s channel=%s history_messages=%d context_loaded=%s context_keys=%s",
                session_id,
                session.user_id,
                msg.channel,
                len(history),
                context is not None,
                sorted(context.keys()) if isinstance(context, dict) else [],
            )

        reply_text = await self._llm.run(
            msg,
            history=history,
            context=context,
            user_id=resolved_user_id,
        )
        outbound = OutboundMessage(
            channel=msg.channel,
            account_id=msg.account_id,
            chat_id=msg.chat_id,
            thread_id=msg.thread_id,
            text=reply_text,
            reply_to=msg.message_id,
            media=[],
        )
        with db_session() as db:
            SessionManager(db).add_turn(session_id, msg, outbound)
        return outbound

    async def route_api_message(
        self,
        user_id: UUID,
        user_content: str,
        session_id: Optional[UUID] = None,
    ) -> tuple[OutboundMessage, UUID]:
        """Route a direct chat-API message for an already-authenticated user.

        Unlike route_to_llm, there is no channel webhook or Linker involved:
        the caller is identified up front via their Tessera JWT. Reuses the
        same SessionManager/LLMRunner plumbing as the channel path so
        session history and context-snapshot behavior stay identical.
        """
        with db_session() as db:
            session_manager = SessionManager(db)
            session = None
            if session_id is not None:
                session = self._get_owned_session(db, session_id, user_id)
            if session is not None:
                msg = self._build_api_inbound_message(
                    user_content, user_id, session.chat_id
                )
            else:
                msg = self._build_api_inbound_message(
                    user_content, user_id, str(uuid4())
                )
                session = session_manager.get_or_create_session(msg, user_id)
            resolved_session_id = session.id
            history = session_manager.get_history_for_llm(resolved_session_id, limit=50)
            context = self._load_context_for_user(db, session.user_id)
            logger.info(
                "Prepared LLM input for API session=%s user_id=%s history_messages=%d context_loaded=%s",
                resolved_session_id,
                user_id,
                len(history),
                context is not None,
            )

        reply_text = await self._llm.run(
            msg,
            history=history,
            context=context,
            user_id=user_id,
        )
        outbound = OutboundMessage(
            channel=API_CHANNEL,
            account_id=None,
            chat_id=msg.chat_id,
            thread_id=None,
            text=reply_text,
            reply_to=msg.message_id,
            media=[],
        )
        with db_session() as db:
            SessionManager(db).add_turn(resolved_session_id, msg, outbound)
        return outbound, resolved_session_id

    def _get_owned_session(self, db: Any, session_id: UUID, user_id: UUID):
        """Look up a session by id, scoped to the requesting user.

        A session_id belonging to a different user is treated the same as
        "not found" rather than surfacing whose session it is.
        """
        session = SessionRepository(db).get_session(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session

    def _build_api_inbound_message(
        self, text: str, user_id: UUID, chat_id: str
    ) -> InboundMessage:
        return InboundMessage(
            channel=API_CHANNEL,
            account_id=None,
            sender_id=str(user_id),
            chat_id=chat_id,
            thread_id=None,
            message_id=str(uuid4()),
            text=text,
            media=[],
            timestamp=datetime.now(timezone.utc),
            raw={},
        )

    def _load_context_for_user(self, db: Any, user_id: Optional[UUID]) -> Optional[Any]:
        """Load latest context snapshot for the user; trigger sync if missing."""
        if not user_id:
            logger.info("Skipping context load because user_id is missing")
            return None
        snapshot_repo = ContextSnapshotRepository(db)
        snapshot = snapshot_repo.get_latest_snapshot(user_id)
        if snapshot:
            payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
            logger.info(
                "Loaded context snapshot for user_id=%s keys=%s",
                user_id,
                sorted(payload.keys()),
            )
            return snapshot.payload
        sync_context_for_user_task.delay(str(user_id))
        logger.info("No context snapshot found for user_id=%s; queued sync", user_id)
        return None

    def _create_link_outbound_message(self, msg: InboundMessage) -> OutboundMessage:
        link_token = self._linker.generate_link_token(msg.channel, msg.sender_id)
        link_url = get_settings().link_url.format(
            channel=msg.channel, link_token=link_token
        )
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

    def _create_link_resolution_error_outbound_message(
        self, msg: InboundMessage
    ) -> OutboundMessage:
        return OutboundMessage(
            channel=msg.channel,
            account_id=msg.account_id,
            chat_id=msg.chat_id,
            thread_id=msg.thread_id,
            text=LINK_RESOLUTION_ERROR_MESSAGE,
            reply_to=msg.message_id,
            media=[],
        )

    def is_linked(self, channel: str, external_id: str) -> bool:
        return self._linker.is_account_linked(channel, external_id)
