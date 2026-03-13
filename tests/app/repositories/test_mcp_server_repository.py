"""Tests for MCPServerService."""

import pytest

from app.schemas.mcp_server import MCPServerCreate, MCPServerUpdate
from app.repositories.mcp_server_repository import MCPServerRepository


def test_create_mcp_server_with_nullable_credential_id(db):
    """Create MCP server with credential_id=None."""
    svc = MCPServerRepository(db)
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
    svc = MCPServerRepository(db)
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
    svc = MCPServerRepository(db)
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


def test_get_enabled_servers_returns_only_enabled(db):
    """get_enabled_servers returns only enabled servers, ordered by server_id."""
    svc = MCPServerRepository(db)
    svc.create_mcp_server(
        MCPServerCreate(
            server_id="alpha",
            name="Alpha",
            url="https://alpha.example/mcp",
            enabled=True,
        )
    )
    svc.create_mcp_server(
        MCPServerCreate(
            server_id="bravo",
            name="Bravo",
            url="https://bravo.example/mcp",
            enabled=False,
        )
    )
    svc.create_mcp_server(
        MCPServerCreate(
            server_id="charlie",
            name="Charlie",
            url="https://charlie.example/mcp",
            enabled=True,
        )
    )
    enabled = svc.get_enabled_servers()
    assert len(enabled) == 2
    assert [s.server_id for s in enabled] == ["alpha", "charlie"]
