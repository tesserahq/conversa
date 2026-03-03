"""Tests for MCPServerService."""

import pytest

from app.schemas.mcp_server import MCPServerCreate, MCPServerUpdate
from app.services.mcp_server_service import MCPServerService


def test_create_mcp_server_with_nullable_credential_id(db):
    """Create MCP server with credential_id=None."""
    svc = MCPServerService(db)
    created = svc.create_mcp_server(
        MCPServerCreate(
            server_id="linden",
            name="Linden MCP",
            url="https://api.mylinden.family/mcp",
            credential_id=None,
            tool_prefix="linden",
            tool_cache_ttl_seconds=300,
            enabled=True,
            extended_info={"region": "global"},
        )
    )
    assert created.id is not None
    assert created.server_id == "linden"
    assert created.credential_id is None
    assert created.extended_info == {"region": "global"}


def test_create_mcp_server_duplicate_server_id_fails(db):
    """Creating duplicate server_id raises ValueError."""
    svc = MCPServerService(db)
    payload = MCPServerCreate(
        server_id="linden",
        name="Linden MCP",
        url="https://api.mylinden.family/mcp",
    )
    svc.create_mcp_server(payload)
    with pytest.raises(ValueError, match="already exists"):
        svc.create_mcp_server(payload)


def test_update_mcp_server_can_set_credential_id_to_none(db, setup_credential):
    """Updating with credential_id=None clears credential binding."""
    svc = MCPServerService(db)
    created = svc.create_mcp_server(
        MCPServerCreate(
            server_id="linden",
            name="Linden MCP",
            url="https://api.mylinden.family/mcp",
            credential_id=setup_credential.id,
        )
    )
    updated = svc.update_mcp_server(
        created.id,
        MCPServerUpdate(
            name="Linden MCP Updated",
            credential_id=None,
        ),
    )
    assert updated is not None
    assert updated.name == "Linden MCP Updated"
    assert updated.credential_id is None
