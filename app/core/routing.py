from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from app.adapters.mcp_toolset import MCPToolset
from app.channels.envelope import InboundMessage, OutboundMessage
from app.config import get_settings
from app.core.linker import Linker
from app.repositories.context_snapshot_repository import ContextSnapshotRepository
from app.repositories.mcp_tool_catalog_repository import MCPToolCatalogRepository
from app.mcp.tool_executor import MCPToolExecutor
from app.utils.metrics import CONTEXT_SNAPSHOT_AGE_SECONDS
from app.repositories.session_manager import SessionManager
from app.tasks.context_sync_task import sync_context_for_user_task
from app.utils.db.db_session_helper import db_session
from app.workers.llm import LLMRunner, build_llm_runner_from_env
import asyncio

WELCOME_MESSAGE = "Hello and welcome. Please click the link below to connect your {channel} account to your Linden account so we can continue. This link is valid for 10 minutes: {link_url}"
LINK_RESOLUTION_ERROR_MESSAGE = "Sorry, we couldn't verify your linked account right now. Please try again in a moment."


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
            toolsets = await self._get_toolsets_for_user(db, session.user_id)

        reply_text = await self._llm.run(
            msg,
            history=history,
            context=context,
            toolsets=toolsets,
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

    def _load_context_for_user(self, db: Any, user_id: Optional[UUID]) -> Optional[Any]:
        """Load latest context snapshot for the user; record metrics or trigger sync if missing."""
        if not user_id:
            return None
        snapshot_repo = ContextSnapshotRepository(db)
        snapshot = snapshot_repo.get_latest_snapshot(user_id)
        if snapshot:
            age_seconds = (
                datetime.now(timezone.utc) - snapshot.generated_at
            ).total_seconds()
            CONTEXT_SNAPSHOT_AGE_SECONDS.labels(user_id=str(user_id)).set(age_seconds)
            return snapshot.payload
        sync_context_for_user_task.delay(str(user_id))
        return None

    async def _get_toolsets_for_user(
        self, db: Any, user_id: Optional[UUID]
    ) -> Optional[list[MCPToolset]]:
        """Build MCP toolsets for the user when MCP tools are enabled."""
        if not get_settings().mcp_tools_enabled:
            return None
        catalog_repo = MCPToolCatalogRepository(db)
        mcp_tools = await catalog_repo.get_tools_for_request(user_id=user_id)
        if not mcp_tools:
            return None
        executor = MCPToolExecutor(db)
        return [
            MCPToolset(
                mcp_tools,
                executor,
                user_id=user_id,
            )
        ]

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
