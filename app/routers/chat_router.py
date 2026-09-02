"""Direct chat API: OpenAI-shaped /chat/completions backed by Conversa sessions."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from tessera_sdk.server.dependencies.auth import get_current_user

from app.auth.rbac import build_rbac_dependencies
from app.core.routing import Router

chat_router = APIRouter(tags=["Chat"])


def get_router() -> Router:
    # Deferred import: app.core.app_state constructs a Router() (and, via
    # LLMRunner, hits the DB for the system prompt) at import time, so it
    # must not be imported at module scope here — main.py's lifespan defers
    # it the same way.
    from app.core.app_state import state

    return state.router


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_CHAT = "chat"
rbac = build_rbac_dependencies(resource=RESOURCE_CHAT, domain_resolver=infer_domain)

SESSION_ID_HEADER = "X-Conversa-Session-Id"


class ChatMessageInput(BaseModel):
    role: str
    content: str


class ChatCompletionCreate(BaseModel):
    """OpenAI-standard shape, plus an optional session_id for Conversa's
    server-side session continuity. `model` is intentionally not accepted:
    model/config selection stays server-side (Modela's default chat config).
    """

    messages: list[ChatMessageInput] = Field(min_length=1)
    stream: bool = False
    session_id: Optional[UUID] = None


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


@chat_router.post(
    "/chat/completions",
    response_model=ChatCompletionResponseOut,
)
async def create_chat_completion(
    payload: ChatCompletionCreate,
    response: Response,
    _authorized: bool = Depends(rbac["create"]),
    current_user: Any = Depends(get_current_user),
    router: Router = Depends(get_router),
) -> ChatCompletionResponseOut:
    if payload.stream:
        # Streaming support lands in a follow-up (tesserahq/conversa#65).
        raise HTTPException(
            status_code=422,
            detail="stream=true is not yet supported on this endpoint.",
        )

    user_content = payload.messages[-1].content
    outbound, session_id = await router.route_api_message(
        user_id=current_user.id,
        user_content=user_content,
        session_id=payload.session_id,
    )
    response.headers[SESSION_ID_HEADER] = str(session_id)

    return ChatCompletionResponseOut(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        object="chat.completion",
        created=int(time.time()),
        model="conversa",
        choices=[
            ChatCompletionChoiceOut(
                index=0,
                message=ChatCompletionMessageOut(
                    role="assistant", content=outbound.text or ""
                ),
                finish_reason="stop",
            )
        ],
    )
