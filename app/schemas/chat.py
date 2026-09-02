"""Pydantic schemas for the direct chat API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


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
    session_id: UUID | None = None


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
