from __future__ import annotations

from typing import Optional

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.litellm import LiteLLMProvider

from app.channels.envelope import InboundMessage
from app.config import get_settings
from app.infra.logging_config import get_logger

logger = get_logger()


class LLMRunner:
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> None:
        provider = LiteLLMProvider(api_key=api_key, api_base=api_base)
        model = OpenAIChatModel(model_name, provider=provider)
        self._agent = Agent(model)

    async def run(self, msg: InboundMessage) -> str:
        prompt = msg.text or ""
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
            "LITELLM_API_KEY33 is not set; set it to a valid OpenAI or LiteLLM API key to avoid 401 errors."
        )
    return LLMRunner(
        model_name=settings.llm_model,
        api_key=settings.litellm_api_key,
        api_base=settings.litellm_api_base,
    )
