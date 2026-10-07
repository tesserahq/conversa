"""Typed completion output shared by Modela, routing, and HTTP adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from tessera_sdk.infra.events import Event
from tessera_sdk.mcp import TruncationMarker


@dataclass(frozen=True)
class CompletionTextDelta:
    """Assistant text produced incrementally by Modela."""

    text: str


@dataclass(frozen=True)
class CompletionStreamExtension:
    """SDK-owned extension value forwarded by the chat transport."""

    wire_field: ClassVar[str]

    def wire_value(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class CompletionEvent(CompletionStreamExtension):
    """A committed Tessera domain event from Modela."""

    event: Event
    wire_field = "event"

    def wire_value(self) -> dict:
        return self.event.model_dump(mode="json")


@dataclass(frozen=True)
class CompletionTruncation(CompletionStreamExtension):
    """Notice that Modela omitted later records from the event channel."""

    marker: TruncationMarker
    wire_field = "truncation"

    def wire_value(self) -> dict:
        return self.marker.model_dump(mode="json")


CompletionStreamItem = CompletionTextDelta | CompletionEvent | CompletionTruncation


@dataclass(frozen=True)
class CompletionResult:
    """Complete assistant text plus response-only event-channel metadata."""

    text: str
    events: tuple[Event, ...] = ()
    truncations: tuple[TruncationMarker, ...] = ()


class CompletionFailure(Exception):
    """A completion failure retaining events observed before it failed."""

    def __init__(
        self,
        original_error: Exception,
        *,
        events: tuple[Event, ...] = (),
        truncations: tuple[TruncationMarker, ...] = (),
    ) -> None:
        super().__init__(str(original_error))
        self.original_error = original_error
        self.events = events
        self.truncations = truncations
