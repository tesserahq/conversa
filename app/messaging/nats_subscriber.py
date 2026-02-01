"""Utilities for subscribing to NATS events using FastStream."""

# pyright: reportMissingImports=false
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from typing import Awaitable, Callable, Mapping, Optional, Set

from faststream import FastStream
from faststream.nats import NatsBroker

from app.config import Settings, get_settings

MessageHandler = Callable[..., Awaitable[None]]


class NatsEventSubscriber:
    """Convenience wrapper around FastStream's NATS broker."""

    def __init__(
        self,
        broker: Optional[NatsBroker] = None,
        *,
        app: Optional[FastStream] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Initialize the subscriber with the configured broker and app.

        Args:
            broker: Optional broker instance to reuse (useful for testing).
            app: Optional FastStream app instance to reuse (useful for testing).
            settings: Optional settings instance. When omitted the global
                application settings are loaded.
        """
        self.settings = settings or get_settings()
        self.broker = broker or NatsBroker(self.settings.nats_url)
        self.app = app or FastStream(self.broker)
        self._registered_subjects: Set[str] = set()

    def subscribe(
        self,
        subject: str,
        handler: MessageHandler,
        *,
        queue: Optional[str] = None,
    ) -> None:
        """Register a handler for a subject."""
        queue_name = queue or self.settings.nats_queue or None
        subscriber = self.broker.subscriber(subject, queue=queue_name)
        subscriber(handler)
        self._registered_subjects.add(subject)

    def subscribe_bulk(
        self,
        handlers: Mapping[str, MessageHandler],
        *,
        queue: Optional[str] = None,
    ) -> None:
        """Register a mapping of subject names to handler callables."""
        for subject, handler in handlers.items():
            self.subscribe(subject, handler, queue=queue)

    def run(self, **kwargs) -> None:
        """Start the FastStream application to process subscriptions."""
        if not self.settings.nats_enabled:
            raise RuntimeError("NATS subscriptions are disabled in configuration.")
        self.app.run(**kwargs)

    @property
    def registered_subjects(self) -> Set[str]:
        """Return the set of subjects currently registered."""
        return set(self._registered_subjects)
