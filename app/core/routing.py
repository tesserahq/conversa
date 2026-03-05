from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from app.adapters.mcp_toolset import MCPToolset
from app.channels.envelope import InboundMessage, OutboundMessage
from app.config import get_settings
from app.core.linker import Linker
from app.services.context_snapshot_service import ContextSnapshotService
from app.services.mcp_tool_catalog_service import MCPToolCatalogService
from app.services.mcp_tool_executor import MCPToolExecutor
from app.utils.metrics import CONTEXT_SNAPSHOT_AGE_SECONDS
from app.services.session_manager import SessionManager
from app.tasks.context_sync_task import sync_context_for_user_task
from app.utils.db.db_session_helper import db_session
from app.workers.llm import LLMRunner, build_llm_runner_from_env

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
            # Load session and history
            session_manager = SessionManager(db)
            session = session_manager.get_or_create_session(msg, user_id)
            history = session_manager.get_history_for_llm(session.id, limit=50)

            # Load context and toolsets
            context = self._load_context_for_user(db, session.user_id)
            toolsets = await self._get_toolsets_for_user(db, session.user_id)

            reply_text = await self._llm.run(
                msg,
                history=history,
                context=context,
                toolsets=toolsets,
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
            session_manager.add_turn(session.id, msg, outbound)
        return outbound

    def _load_context_for_user(self, db: Any, user_id: Optional[UUID]) -> Optional[Any]:
        """Load latest context snapshot for the user; record metrics or trigger sync if missing."""
        if not user_id:
            return None
        snapshot_svc = ContextSnapshotService(db)
        snapshot = snapshot_svc.get_latest_snapshot(user_id)
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
        catalog_svc = MCPToolCatalogService(db)
        mcp_tools = await catalog_svc.get_tools_for_request(user_id=user_id)
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
        link_url = get_settings().link_url.format(link_token=link_token)
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
