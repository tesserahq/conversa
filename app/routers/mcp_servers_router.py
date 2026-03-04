"""MCP servers API: CRUD for the MCP Server Registry."""

from typing import Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.auth.rbac import build_rbac_dependencies
from app.commands.mcp_servers import (
    CreateMcpServerCommand,
    DeleteMcpServerCommand,
    RefreshMcpServerToolsCommand,
    UpdateMcpServerCommand,
)
from app.db import get_db
from app.models.mcp_server import MCPServer
from app.routers.utils.dependencies import get_mcp_server_by_id
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerRead,
    MCPServerUpdate,
    MCPToolsRefreshResponse,
)
from app.services.mcp_server_service import MCPServerService
from tessera_sdk.utils.auth import get_current_user  # type: ignore[import-untyped]

router = APIRouter(
    prefix="/mcp-servers",
    tags=["mcp-servers"],
    responses={404: {"description": "Not found"}},
)


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_MCP_SERVERS = "mcp_server"
rbac = build_rbac_dependencies(
    resource=RESOURCE_MCP_SERVERS,
    domain_resolver=infer_domain,
)


@router.get("", response_model=Page[MCPServerRead])
def list_mcp_servers(
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[MCPServerRead]:
    """List all MCP servers with pagination."""
    svc = MCPServerService(db)
    query = svc.get_mcp_servers_query()
    return paginate(query, params=params)


@router.post("", response_model=MCPServerRead, status_code=201)
def create_mcp_server(
    data: MCPServerCreate,
    _authorized: bool = Depends(rbac["create"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MCPServerRead:
    """Create a new MCP server."""
    command = CreateMcpServerCommand(db)
    return command.execute(
        data,
        created_by_id=getattr(_current_user, "id", None),
    )


@router.get("/{id}", response_model=MCPServerRead)
def get_mcp_server(
    mcp_server: MCPServer = Depends(get_mcp_server_by_id),
    _authorized: bool = Depends(rbac["read"]),
    _current_user=Depends(get_current_user),
) -> MCPServerRead:
    """Get an MCP server by ID."""
    return mcp_server


@router.patch("/{id}", response_model=MCPServerRead)
def update_mcp_server(
    data: MCPServerUpdate,
    mcp_server: MCPServer = Depends(get_mcp_server_by_id),
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MCPServerRead:
    """Update an MCP server."""
    command = UpdateMcpServerCommand(db)
    updated = command.execute(
        cast(UUID, mcp_server.id),
        data,
        updated_by_id=getattr(_current_user, "id", None),
    )

    return updated


@router.post(
    "/{id}/refresh-tools",
    response_model=MCPToolsRefreshResponse,
)
async def refresh_mcp_server_tools(
    mcp_server: MCPServer = Depends(get_mcp_server_by_id),
    _authorized: bool = Depends(rbac["update"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MCPToolsRefreshResponse:
    """Force-refresh the tool catalog for this MCP server."""
    command = RefreshMcpServerToolsCommand(db)
    return await command.execute(
        mcp_server,
        user_id=getattr(_current_user, "id", None),
    )


@router.delete("/{id}", status_code=204)
def delete_mcp_server(
    mcp_server: MCPServer = Depends(get_mcp_server_by_id),
    _authorized: bool = Depends(rbac["delete"]),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft delete an MCP server."""
    command = DeleteMcpServerCommand(db)
    command.execute(
        cast(UUID, mcp_server.id),
        deleted_by_id=getattr(_current_user, "id", None),
    )
