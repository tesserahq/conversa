"""Tests for app.mcp.client_factory."""

import pytest

from app.mcp.client_factory import client_context


@pytest.mark.asyncio
async def test_client_context_passes_url_and_headers():
    """client_context builds transport with given url and headers."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with (
        patch("app.mcp.client_factory.StreamableHttpTransport") as transport_cls,
        patch("app.mcp.client_factory.Client") as client_cls,
    ):
        transport_instance = MagicMock()
        transport_cls.return_value = transport_instance
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client_instance

        async with client_context(
            "https://api.example.com/mcp",
            headers={"Authorization": "Bearer token123"},
        ) as client:
            assert client is client_instance
            transport_cls.assert_called_once_with(
                "https://api.example.com/mcp",
                headers={"Authorization": "Bearer token123"},
            )
            client_cls.assert_called_once_with(transport_instance)


@pytest.mark.asyncio
async def test_client_context_with_empty_headers():
    """client_context uses empty dict when headers is None."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with (
        patch("app.mcp.client_factory.StreamableHttpTransport") as transport_cls,
        patch("app.mcp.client_factory.Client") as client_cls,
    ):
        transport_instance = MagicMock()
        transport_cls.return_value = transport_instance
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client_instance

        async with client_context("https://other.example/mcp", headers=None) as _:
            transport_cls.assert_called_once_with(
                "https://other.example/mcp",
                headers={},
            )
