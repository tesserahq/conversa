"""Build FastMCP Client from url + headers (no DB, no credential resolution)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def _sanitize_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Ensure headers are a flat dict of string keys and values for HTTP."""
    if not headers:
        return {}
    return {
        str(k): str(v)
        for k, v in headers.items()
        if v is not None and isinstance(v, (str, int, float))
    }


@asynccontextmanager
async def client_context(
    url: str,
    headers: dict[str, str] | None = None,
) -> AsyncIterator[Client]:
    """
    Async context manager that yields a FastMCP Client for the given URL and headers.

    Caller is responsible for resolving headers (e.g. via CredentialRepository).
    """
    safe_headers = _sanitize_headers(headers)
    transport = StreamableHttpTransport(url=url, headers=safe_headers)
    client = Client(transport)
    async with client:
        yield client
