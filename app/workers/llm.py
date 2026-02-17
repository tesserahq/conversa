from __future__ import annotations

from typing import Any, List, Optional

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.litellm import LiteLLMProvider

from app.channels.envelope import InboundMessage
from app.config import get_settings
from app.infra.logging_config import get_logger
from app.utils.db.db_session_helper import db_session
from app.services.system_prompt_service import SystemPromptService

logger = get_logger()

SYSTEM_PROMPT_NAME = "default"


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
        self._agent = Agent(model, system_prompt=system_prompt or None)

    async def run(
        self,
        msg: InboundMessage,
        history: Optional[List[dict[str, str]]] = None,
    ) -> str:
        prompt = msg.text or ""
        message_history = _history_to_message_list(history or [])
        if message_history:
            result = await self._agent.run(
                prompt,
                message_history=message_history,
            )
        else:
            result = await self._agent.run(prompt)
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
    with db_session() as db:
        system_prompt = SystemPromptService(db).get_current_content(SYSTEM_PROMPT_NAME)

    return LLMRunner(
        model_name=settings.llm_model,
        api_key=settings.litellm_api_key,
        api_base=settings.litellm_api_base,
        system_prompt=system_prompt,
    )
