from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .envelope import InboundMessage, OutboundMessage


@dataclass(frozen=True)
class ChannelMeta:
    label: str
    docs: Optional[str] = None


@dataclass(frozen=True)
class ChannelCapabilities:
    chat_types: list[str]
    supports_webhook: bool = False
    supports_polling: bool = False
    supports_reactions: bool = False
    supports_media: bool = False


class ChannelPlugin(Protocol):
    id: str
    meta: ChannelMeta
    capabilities: ChannelCapabilities

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def handle_inbound(self, msg: InboundMessage) -> None: ...
    async def send(self, msg: OutboundMessage) -> None: ...
