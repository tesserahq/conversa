"""Pydantic schemas for the direct chat API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from tessera_sdk.clients.modela import ChatCompletionExtensions
from tessera_sdk.mcp import CompletionInclude


class ChatMessageInput(BaseModel):
    role: str
    content: str


class ChatCompletionCreate(BaseModel):
    """Request for a direct chat completion.

    The shape follows OpenAI's chat completions API and adds an optional
    session ID for Conversa's server-side session continuity. Model selection
    intentionally remains server-side.
    """

    messages: list[ChatMessageInput] = Field(min_length=1)
    stream: bool = False
    include: list[CompletionInclude] | None = None
    session_id: UUID | None = None
    client_context: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Free-form ambient context from the calling UI (e.g. account_id, "
            "todo_list_id), surfaced to the model in its system prompt. "
            "Advisory only — not an authorization grant, must not be trusted "
            "for access control decisions."
        ),
    )

    @model_validator(mode="after")
    def allow_application_event_channel_only(self):
        unsupported = set(self.include or ()) - {CompletionInclude.EVENTS}
        if unsupported:
            raise ValueError("Conversa only supports include=['events']")
        return self

    @property
    def wants_events(self) -> bool:
        return CompletionInclude.EVENTS in (self.include or ())


class ChatCompletionMessageOut(BaseModel):
    role: str
    content: str


class ChatCompletionChoiceOut(BaseModel):
    index: int
    message: ChatCompletionMessageOut
    finish_reason: str


class ChatCompletionResponseOut(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[ChatCompletionChoiceOut]
    extensions: ChatCompletionExtensions | None = None
