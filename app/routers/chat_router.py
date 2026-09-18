"""Direct chat API: OpenAI-shaped /chat/completions backed by Conversa sessions."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Optional
from json import JSONDecodeError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from tessera_sdk.server.dependencies.auth import get_current_user

from app.auth.rbac import build_rbac_dependencies
from app.core.rate_limit import enforce_user_rate_limit
from app.core.routing import Router
from app.schemas.chat import (
    ChatCompletionChoiceOut,
    ChatCompletionCreate,
    ChatCompletionMessageOut,
    ChatCompletionResponseOut,
)

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
    project_id = request.query_params.get("project_id")

    if not project_id:
        body_bytes = await request.body()
        if body_bytes:
            try:
                body = json.loads(body_bytes)
                project_id = body.get("project_id")
            except JSONDecodeError:
                pass

    project_id = project_id or "*"
    request.state.project_id = project_id
    return project_id


RESOURCE_CHAT = "chat"
rbac = build_rbac_dependencies(resource=RESOURCE_CHAT, domain_resolver=infer_domain)

SESSION_ID_HEADER = "X-Conversa-Session-Id"


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
    request: Request,
    response: Response,
    _authorized: bool = Depends(rbac["create"]),
    _rate_limited: None = Depends(_rate_limit_chat),
    current_user: Any = Depends(get_current_user),
    router: Router = Depends(get_router),
):
    user_content = payload.messages[-1].content
    project_id = getattr(request.state, "project_id", "*")

    if payload.stream:
        session_id, delta_gen = await router.stream_api_message(
            user_id=current_user.id,
            user_content=user_content,
            session_id=payload.session_id,
            project_id=project_id,
            client_context=payload.client_context,
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
        project_id=project_id,
        client_context=payload.client_context,
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
