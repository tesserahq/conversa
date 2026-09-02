"""Direct chat API: OpenAI-shaped /chat/completions backed by Conversa sessions."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from tessera_sdk.server.dependencies.auth import get_current_user

from app.auth.rbac import build_rbac_dependencies
from app.core.rate_limit import enforce_user_rate_limit
from app.core.routing import Router

chat_router = APIRouter(tags=["Chat"])

_rate_limit_chat = enforce_user_rate_limit("chat")


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


async def _sse_chunks(
    delta_gen: AsyncIterator[str], completion_id: str, created_ts: int
) -> AsyncIterator[str]:
    """Render text deltas as OpenAI chat.completion.chunk SSE events,
    matching the shape Modela's own /chat/completions already emits.
    """
    first = True
    async for delta in delta_gen:
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": "conversa",
            "choices": [
                {
                    "index": 0,
                    "delta": (
                        {"role": "assistant", "content": delta}
                        if first
                        else {"content": delta}
                    ),
                    "finish_reason": None,
                }
            ],
        }
        first = False
        yield f"data: {json.dumps(chunk)}\n\n"
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": "conversa",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


@chat_router.post(
    "/chat/completions",
    response_model=ChatCompletionResponseOut,
)
async def create_chat_completion(
    payload: ChatCompletionCreate,
    response: Response,
    _authorized: bool = Depends(rbac["create"]),
    _rate_limited: None = Depends(_rate_limit_chat),
    current_user: Any = Depends(get_current_user),
    router: Router = Depends(get_router),
):
    user_content = payload.messages[-1].content

    if payload.stream:
        session_id, delta_gen = await router.stream_api_message(
            user_id=current_user.id,
            user_content=user_content,
            session_id=payload.session_id,
        )
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_ts = int(time.time())
        return StreamingResponse(
            _sse_chunks(delta_gen, completion_id, created_ts),
            media_type="text/event-stream",
            headers={SESSION_ID_HEADER: str(session_id)},
        )

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
