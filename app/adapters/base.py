"""
Platform adapter interface.

Adapters encapsulate platform-specific logic and expose a normalized
message format to the Conversa core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.conversa import InboundMessage, OutboundMessage, OutboundSendResult


class BasePlatformAdapter(ABC):
    """Contract for platform adapters. New platforms implement this interface."""

    @abstractmethod
    def parse_webhook(self, raw_payload: dict[str, Any]) -> InboundMessage:
        """Parse raw webhook payload into normalized inbound message. Raise if invalid."""
        ...

    @abstractmethod
    async def send(self, outbound: OutboundMessage) -> OutboundSendResult:
        """Send normalized outbound message via platform API. Return success and optional message_id."""
        ...

    def verify_webhook(
        self, secret: Optional[str], request_headers: Optional[dict[str, str]] = None
    ) -> bool:
        """
        Verify webhook request (e.g. secret token). Override if platform supports it.
        Return True if valid or verification not required; False to reject.
        """
        return True
