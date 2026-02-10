from pydantic_ai import Agent


class AIBuddy:
    def __init__(self):
        self.agent = Agent(
            "gateway/openai:gpt-4o-mini",
            instructions="Be concise, reply with one sentence.",
        )

    async def ask(self, prompt: str) -> str:
        """
        Generate a concise, single-sentence response from the AI agent using the given prompt.
        Use this from async code (e.g. FastAPI); do not use run_sync when the event loop is already running.

        Args:
            prompt (str): The prompt or question to send to the AI.

        Returns:
            str: The AI agent's concise response.
        """
        result = await self.agent.run(prompt)
        return result.output
