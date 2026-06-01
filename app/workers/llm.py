from __future__ import annotations

import asyncio
import json
from typing import Any, List, Optional
from uuid import UUID

from tessera_sdk.clients.modela import CompletionMessage, ModelaClient

from app.channels.envelope import InboundMessage
from app.config import get_settings
from app.constants.default_system_prompt import DefaultSystemPrompt
from app.infra.logging_config import get_logger
from app.repositories.mcp_delegated_token_repository import MCPDelegatedTokenRepository
from app.repositories.system_prompt_repository import SystemPromptRepository
from app.utils.db.db_session_helper import db_session

logger = get_logger()

SYSTEM_PROMPT_NAME = "default"


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


def _build_completion_messages(
    system_prompt: str,
    history: List[dict[str, str]],
    user_content: str,
    context: Optional[dict[str, Any]] = None,
) -> List[CompletionMessage]:
    """Build Modela messages: system prompt, history, then current user turn."""
    full_prompt = system_prompt
    if context:
        ctx_block = _format_context_for_prompt(context)
        if ctx_block:
            full_prompt = system_prompt.rstrip() + ctx_block

    messages: List[CompletionMessage] = [
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
    def __init__(
        self,
        model_name: str,
        system_prompt: Optional[str] = None,
        *,
        modela_audience: str,
        modela_scopes: str,
        token_repo: Optional[MCPDelegatedTokenRepository] = None,
        modela_base_url: Optional[str] = None,
    ) -> None:
        logger.info("Initializing LLM runner with model %s", model_name)
        self._model_name = model_name
        self._system_prompt = system_prompt or ""
        self._modela_audience = modela_audience
        self._modela_scopes = modela_scopes
        self._token_repo = token_repo or MCPDelegatedTokenRepository()
        self._modela_base_url = modela_base_url

    async def run(
        self,
        msg: InboundMessage,
        history: Optional[List[dict[str, str]]] = None,
        context: Optional[dict[str, Any]] = None,
        toolsets: Optional[List[Any]] = None,
        *,
        user_id: Optional[UUID] = None,
    ) -> str:
        if user_id is None:
            raise ValueError("LLM completion requires user_id for delegated auth")

        if toolsets:
            logger.debug("MCP toolsets present but Modela handles tools internally")

        messages = _build_completion_messages(
            self._system_prompt,
            history or [],
            msg.text or "",
            context=context,
        )
        token = self._token_repo.get_access_token(
            user_id=user_id,
            audience=self._modela_audience,
            scopes=self._modela_scopes,
        )
        logger.info(f"token: {token}")
        client_kwargs: dict[str, Any] = {"api_token": token}
        if self._modela_base_url is not None:
            client_kwargs["base_url"] = self._modela_base_url
        client = ModelaClient(**client_kwargs)

        response = await asyncio.to_thread(
            client.complete,
            messages=messages,
            model=self._model_name,
            project_id="*",
        )
        if not response.choices:
            raise ValueError("Modela returned no completion choices")
        return response.choices[0].message.content


def build_llm_runner_from_env() -> LLMRunner:
    settings = get_settings()
    logger.info(
        "LLM runner config: model=%s, modela_audience=%s",
        settings.llm_model,
        settings.modela_audience,
    )

    system_prompt = _get_system_prompt()

    return LLMRunner(
        model_name=settings.llm_model,
        system_prompt=system_prompt,
        modela_audience=settings.modela_audience,
        modela_scopes=settings.modela_scopes,
    )


def _get_system_prompt() -> str:
    with db_session() as db:
        system_prompt = SystemPromptRepository(db).get_current_content(
            SYSTEM_PROMPT_NAME
        )
        if system_prompt:
            return system_prompt

    return DefaultSystemPrompt.CONTENT
