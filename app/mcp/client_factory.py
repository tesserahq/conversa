"""Build FastMCP Client from url + headers (no DB, no credential resolution)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


@asynccontextmanager
async def client_context(
    url: str,
    headers: dict[str, str] | None = None,
) -> AsyncIterator[Client]:
    """
    Async context manager that yields a FastMCP Client for the given URL and headers.

    Caller is responsible for resolving headers (e.g. via CredentialService).
    """
    transport = StreamableHttpTransport(url, headers=headers or {})
    client = Client(transport)
    async with client:
        yield client
