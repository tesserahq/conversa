from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.litellm import LiteLLMProvider

from app.channels.envelope import InboundMessage
from app.config import get_settings
from app.infra.logging_config import get_logger
from app.utils.db.db_session_helper import db_session
from app.services.system_prompt_service import SystemPromptService
from app.constants.default_system_prompt import DefaultSystemPrompt
from pydantic_ai.messages import (
    ModelRequest,
    SystemPromptPart,
)

logger = get_logger()

SYSTEM_PROMPT_NAME = "default"


def add_the_date_and_time() -> str:
    """Return the current date and time. Use when the user asks for today's date or what day it is."""
    return f"The date and time is {datetime.now()}."


def add_the_user_name() -> str:
    """Return the user's name. Use when the user asks for their name."""
    return f"The user's name is Peter"


def _history_to_message_list(history: List[dict[str, str]]) -> List[Any]:
    """Convert list of {role, content} to pydantic_ai ModelMessage list for message_history."""
    try:
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            SystemPromptPart,
            TextPart,
            UserPromptPart,
        )
    except ImportError:
        return []
    out: List[Any] = []
    for item in history:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            out.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            out.append(ModelResponse(parts=[TextPart(content=content)]))
        elif role == "system":
            out.append(ModelRequest(parts=[SystemPromptPart(content=content)]))
    return out


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


def _message_list_with_system_prompt(
    system_prompt: str,
    history: List[dict[str, str]],
    context: Optional[dict[str, Any]] = None,
) -> List[Any]:
    """Build message_history with system prompt always first, then conversation history."""

    # https://github.com/pydantic/pydantic-ai/issues/4039
    # https://ai.pydantic.dev/agent/#system-prompts
    full_prompt = system_prompt
    if context:
        ctx_block = _format_context_for_prompt(context)
        if ctx_block:
            full_prompt = system_prompt.rstrip() + ctx_block
    system_message = ModelRequest(parts=[SystemPromptPart(content=full_prompt)])
    rest = _history_to_message_list(history)
    return [system_message] + rest


class LLMRunner:
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        provider = LiteLLMProvider(api_key=api_key, api_base=api_base)
        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(f"Initializing LLM runner with model {model_name}")
        self._system_prompt = system_prompt or ""
        self._agent = Agent(
            model,
            tools=[add_the_date_and_time, add_the_user_name],
        )

    async def run(
        self,
        msg: InboundMessage,
        history: Optional[List[dict[str, str]]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        prompt = msg.text or ""
        message_history = _message_list_with_system_prompt(
            self._system_prompt,
            history or [],
            context=context,
        )
        result = await self._agent.run(
            prompt,
            message_history=message_history,
        )
        return str(result.output)


def build_llm_runner_from_env() -> LLMRunner:
    settings = get_settings()
    logger.info(
        "LLM runner config: model=%s, api_key=%s, api_base=%s",
        settings.llm_model,
        "set" if settings.litellm_api_key else "not set",
        settings.litellm_api_base or "(default)",
    )
    if not settings.litellm_api_key:
        logger.warning(
            "LITELLM_API_KEY is not set; set it to a valid OpenAI or LiteLLM API key to avoid 401 errors."
        )

    system_prompt = _get_system_prompt()

    return LLMRunner(
        model_name=settings.llm_model,
        api_key=settings.litellm_api_key,
        api_base=settings.litellm_api_base,
        system_prompt=system_prompt,
    )


def _get_system_prompt() -> str:
    print(f"Getting system prompt from database")
    with db_session() as db:
        system_prompt = SystemPromptService(db).get_current_content(SYSTEM_PROMPT_NAME)
        if system_prompt:
            return system_prompt
    print(f"No system prompt found in database, using default")

    return DefaultSystemPrompt.CONTENT
