from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from tessera_sdk.clients.modela import CompletionMessage, ModelaClient, ModelaError
from tessera_sdk.infra.events import Event
from tessera_sdk.mcp import CompletionInclude, TruncationMarker

from app.channels.envelope import InboundMessage
from app.config import get_settings
from app.constants.default_system_prompt import DefaultSystemPrompt
from app.core.completion_output import (
    CompletionEvent,
    CompletionFailure,
    CompletionResult,
    CompletionStreamItem,
    CompletionTextDelta,
    CompletionTruncation,
)
from app.db import session_scope
from app.infra.logging_config import get_logger
from app.repositories.mcp_delegated_token_repository import MCPDelegatedTokenRepository
from app.repositories.system_prompt_repository import SystemPromptRepository

logger = get_logger()

SYSTEM_PROMPT_NAME = "default"


def _summarize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {"present": False, "keys": [], "section_sizes": {}}

    section_sizes: dict[str, int | str] = {}
    for key, value in context.items():
        if isinstance(value, (list, dict)):
            section_sizes[key] = len(value)
        elif value is None:
            section_sizes[key] = 0
        else:
            section_sizes[key] = "scalar"

    return {
        "present": True,
        "keys": sorted(context.keys()),
        "section_sizes": section_sizes,
    }


def _format_context_for_prompt(context: dict[str, Any]) -> str:
    """Format context snapshot for injection into system prompt."""
    parts = []
    if context.get("facts"):
        parts.append("Facts: " + json.dumps(context["facts"], default=str))
    if context.get("recents"):
        parts.append("Recents: " + json.dumps(context["recents"], default=str))
    if context.get("pointers"):
        parts.append("Pointers: " + json.dumps(context["pointers"], default=str))
    if not parts:
        return ""
    return "\n\nUser context (use when relevant):\n" + "\n".join(parts)


def _format_client_context_for_prompt(client_context: dict[str, Any]) -> str:
    """Format UI-supplied ambient context (e.g. account_id, todo_list_id)
    for injection into the system prompt. Advisory only: this is client-
    supplied data, not an authorization grant, so it must never be used in
    place of a real access-control check.
    """
    if not client_context:
        return ""
    return (
        "\n\nCurrent app context (use these values directly instead of "
        "asking the user for them):\n" + json.dumps(client_context, default=str)
    )


def _build_completion_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    user_content: str,
    context: dict[str, Any] | None = None,
    client_context: dict[str, Any] | None = None,
) -> list[CompletionMessage]:
    """Build Modela messages: system prompt, history, then current user turn."""
    full_prompt = system_prompt
    if context:
        ctx_block = _format_context_for_prompt(context)
        if ctx_block:
            full_prompt = full_prompt.rstrip() + ctx_block
    if client_context:
        client_ctx_block = _format_client_context_for_prompt(client_context)
        if client_ctx_block:
            full_prompt = full_prompt.rstrip() + client_ctx_block

    messages: list[CompletionMessage] = [
        CompletionMessage(role="system", content=full_prompt)
    ]
    for item in history:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if role in ("user", "assistant", "system"):
            messages.append(CompletionMessage(role=role, content=content))

    user_content = (user_content or "").strip()
    if user_content:
        messages.append(CompletionMessage(role="user", content=user_content))
    return messages


class LLMRunner:
    """The only place in Conversa that talks to Modela.

    Model/config selection is intentionally not exposed here: Modela resolves
    its own default chat ModelConfig when no `model` is passed, so callers
    never send one.
    """

    def __init__(
        self,
        system_prompt: str | None = None,
        *,
        modela_audience: str,
        modela_scopes: str,
        token_repo: MCPDelegatedTokenRepository | None = None,
        modela_base_url: str | None = None,
    ) -> None:
        logger.info("Initializing LLM runner")
        self._system_prompt = system_prompt or ""
        self._modela_audience = modela_audience
        self._modela_scopes = modela_scopes
        self._token_repo = token_repo or MCPDelegatedTokenRepository()
        self._modela_base_url = modela_base_url

    async def stream(
        self,
        msg: InboundMessage,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
        *,
        user_id: UUID | None = None,
        project_id: str = "*",
        client_context: dict[str, Any] | None = None,
        include_events: bool = False,
    ) -> AsyncIterator[CompletionStreamItem]:
        """Stream typed text and optional event-channel output from Modela.

        Raises ValueError if Modela's stream produces no chunks at all
        (the streaming analogue of a non-streaming response with no choices).
        """
        if user_id is None:
            raise ValueError("LLM completion requires user_id for delegated auth")

        messages = _build_completion_messages(
            self._system_prompt,
            history or [],
            msg.text or "",
            context=context,
            client_context=client_context,
        )
        context_summary = _summarize_context(context)
        user_text_length = len((msg.text or "").strip())
        logger.info(
            "Dispatching Modela streaming request user_id=%s channel=%s session_message_id=%s history_messages=%d completion_messages=%d user_text_length=%d media_items=%d context_present=%s context_keys=%s context_section_sizes=%s",
            user_id,
            msg.channel,
            msg.message_id,
            len(history or []),
            len(messages),
            user_text_length,
            len(msg.media),
            context_summary["present"],
            context_summary["keys"],
            context_summary["section_sizes"],
        )
        token = self._token_repo.get_access_token(
            user_id=user_id,
            audience=self._modela_audience,
            scopes=self._modela_scopes,
        )
        client_kwargs: dict[str, Any] = {"api_token": token, "timeout": 10}
        if self._modela_base_url is not None:
            client_kwargs["base_url"] = self._modela_base_url
        client = ModelaClient(**client_kwargs)

        chunk_count = 0
        reply_length = 0
        stream_kwargs: dict[str, Any] = {
            "messages": messages,
            "project_id": project_id,
        }
        if include_events:
            stream_kwargs["include"] = [CompletionInclude.EVENTS]

        yielded_events: set[tuple] = set()
        dropped_by_channel: dict[CompletionInclude, int] = {}
        try:
            async for chunk in client.stream_complete(**stream_kwargs):
                chunk_count += 1
                extensions = chunk.extensions
                if include_events and extensions is not None:
                    if extensions.event is not None:
                        yielded_events.add(_event_identity(extensions.event))
                        yield CompletionEvent(extensions.event)
                    marker = extensions.truncation
                    if (
                        marker is not None
                        and marker.channel is CompletionInclude.EVENTS
                    ):
                        dropped_by_channel[marker.channel] = marker.dropped_count
                        yield CompletionTruncation(marker)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    reply_length += len(delta)
                    yield CompletionTextDelta(delta)
        except ModelaError as error:
            # Modela repeats committed events in the error body; surface the
            # ones not already delivered inline before propagating the failure.
            if include_events:
                for event in error.events:
                    if _event_identity(event) not in yielded_events:
                        yielded_events.add(_event_identity(event))
                        yield CompletionEvent(event)
                for marker in error.truncations:
                    if marker.dropped_count > dropped_by_channel.get(
                        marker.channel, -1
                    ):
                        dropped_by_channel[marker.channel] = marker.dropped_count
                        yield CompletionTruncation(marker)
            raise

        logger.info(
            "Finished Modela stream user_id=%s chunks=%d reply_text_length=%d",
            user_id,
            chunk_count,
            reply_length,
        )
        if chunk_count == 0:
            raise ValueError("Modela returned no completion choices")

    async def run(
        self,
        msg: InboundMessage,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
        *,
        user_id: UUID | None = None,
        project_id: str = "*",
        client_context: dict[str, Any] | None = None,
    ) -> str:
        """Non-streaming convenience wrapper: joins the full streamed reply."""
        result = await self.collect(
            msg,
            history=history,
            context=context,
            user_id=user_id,
            project_id=project_id,
            client_context=client_context,
        )
        return result.text

    async def collect(
        self,
        msg: InboundMessage,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
        *,
        user_id: UUID | None = None,
        project_id: str = "*",
        client_context: dict[str, Any] | None = None,
        include_events: bool = False,
    ) -> CompletionResult:
        """Collect one completion without persisting response metadata.

        A failure is wrapped in CompletionFailure only when committed events
        were observed, so callers that cannot see events (or saw none) get
        the original exception and the same error contract either way.
        """
        text_parts: list[str] = []
        events: list[Event] = []
        truncations: dict[CompletionInclude, TruncationMarker] = {}
        try:
            async for item in self.stream(
                msg,
                history=history,
                context=context,
                user_id=user_id,
                project_id=project_id,
                client_context=client_context,
                include_events=include_events,
            ):
                if isinstance(item, CompletionTextDelta):
                    text_parts.append(item.text)
                elif isinstance(item, CompletionEvent):
                    events.append(item.event)
                elif isinstance(item, CompletionTruncation):
                    # stream() only yields a later marker when it reports more drops.
                    truncations[item.marker.channel] = item.marker
        except Exception as error:
            if not events:
                raise
            raise CompletionFailure(
                error,
                events=tuple(events),
                truncations=tuple(truncations.values()),
            ) from error
        return CompletionResult(
            text="".join(text_parts),
            events=tuple(events),
            truncations=tuple(truncations.values()),
        )


def _event_identity(event: Event) -> tuple:
    """Identify an event across inline and error-body delivery.

    Event.id defaults to a fresh uuid4 when Modela omits it, so an id that
    was not on the wire cannot identify the event; fall back to its content.
    """
    if "id" in event.model_fields_set:
        return (event.source, event.id)
    return (
        "content",
        json.dumps(
            event.model_dump(mode="json", include=event.model_fields_set),
            sort_keys=True,
        ),
    )


def build_llm_runner_from_env() -> LLMRunner:
    settings = get_settings()
    logger.info(
        "LLM runner config: modela_audience=%s",
        settings.modela_audience,
    )

    system_prompt = _get_system_prompt()

    return LLMRunner(
        system_prompt=system_prompt,
        modela_audience=settings.modela_audience,
        modela_scopes=settings.modela_scopes,
    )


def _get_system_prompt() -> str:
    with session_scope() as db:
        system_prompt = SystemPromptRepository(db).get_current_content(
            SYSTEM_PROMPT_NAME
        )
        if system_prompt:
            return system_prompt

    return DefaultSystemPrompt.CONTENT
