"""Direct chat API: OpenAI-shaped /chat/completions backed by Conversa sessions."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from tessera_sdk.server.dependencies.auth import get_current_user

from app.auth.rbac import build_rbac_dependencies
from app.core.completion_output import (
    CompletionStreamExtension,
    CompletionStreamItem,
)
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


async def infer_domain(request: Request) -> str | None:
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
    item_gen: AsyncIterator[CompletionStreamItem], completion_id: str, created_ts: int
) -> AsyncIterator[str]:
    """Render typed output using Modela's Chat Completions wire shape."""
    first = True
    async for item in item_gen:
        if isinstance(item, CompletionStreamExtension):
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": "conversa",
                "choices": [],
                "extensions": {item.wire_field: item.wire_value()},
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            continue
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": "conversa",
            "choices": [
                {
                    "index": 0,
                    "delta": (
                        {"role": "assistant", "content": item.text}
                        if first
                        else {"content": item.text}
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
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
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
        session_id, item_gen = await router.stream_api_message(
            user_id=current_user.id,
            user_content=user_content,
            session_id=payload.session_id,
            project_id=project_id,
            client_context=payload.client_context,
            include_events=payload.wants_events,
        )
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_ts = int(time.time())
        return StreamingResponse(
            _sse_chunks(item_gen, completion_id, created_ts),
            media_type="text/event-stream",
            headers={SESSION_ID_HEADER: str(session_id)},
        )

    outbound, session_id, result = await router.route_api_completion(
        user_id=current_user.id,
        user_content=user_content,
        session_id=payload.session_id,
        project_id=project_id,
        client_context=payload.client_context,
        include_events=payload.wants_events,
    )
    response.headers[SESSION_ID_HEADER] = str(session_id)

    extensions = None
    if payload.wants_events:
        extension_values = {"events": list(result.events)}
        if result.truncations:
            extension_values["truncations"] = list(result.truncations)
        extensions = extension_values

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
        extensions=extensions,
    )
