from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from app.channels.envelope import InboundMessage, OutboundMessage

InboundHandler = Callable[[InboundMessage], Awaitable[None]]
OutboundHandler = Callable[[OutboundMessage], Awaitable[None]]


@dataclass
class Runtime:
    inbound_handler: InboundHandler
    outbound_handler: OutboundHandler
