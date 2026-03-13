from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.context_source import ContextSource
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.context_source_repository import ContextSourceRepository
from app.repositories.mcp_server_repository import MCPServerRepository
from app.repositories.user_repository import UserRepository


def get_user_by_id(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency to get a user by ID."""
    user = UserRepository(db).get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_context_source_by_id(
    id: UUID,
    db: Session = Depends(get_db),
) -> ContextSource:
    """FastAPI dependency to get a context source by ID."""
    source = ContextSourceRepository(db).get_context_source(id)
    if source is None:
        raise HTTPException(status_code=404, detail="Context source not found")
    return source


def get_mcp_server_by_id(
    id: UUID,
    db: Session = Depends(get_db),
) -> MCPServer:
    """FastAPI dependency to get an MCP server by ID."""
    mcp_server = MCPServerRepository(db).get_mcp_server(id)
    if mcp_server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return mcp_server
