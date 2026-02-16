"""Session key derivation from inbound message (and optional user for DM scope)."""

from __future__ import annotations

from uuid import UUID

from app.channels.envelope import InboundMessage


def build_session_key(msg: InboundMessage, user_id: UUID | None = None) -> str:
    """
    Build a deterministic session key from an inbound message.

    Simple form: {channel}:{chat_id} for DMs; {channel}:{chat_id}:thread:{thread_id}
    when thread_id is present (e.g. Telegram topics). Optional later: include user_id
    for per-user DM continuity across channels.
    """
    key = f"{msg.channel}:{msg.chat_id}"
    if msg.thread_id:
        key = f"{key}:thread:{msg.thread_id}"
    if user_id is not None:
        key = f"{key}:user:{user_id.hex}"
    return key
