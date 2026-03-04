"""Event builders for CloudEvents / NATS."""

from app.events.context_source_events import (
    CONTEXT_SOURCE_CREATED,
    CONTEXT_SOURCE_DELETED,
    CONTEXT_SOURCE_UPDATED,
    build_context_source_created_event,
    build_context_source_deleted_event,
    build_context_source_updated_event,
)
from app.events.credential_events import (
    CREDENTIAL_CREATED,
    build_credential_created_event,
)
from app.events.mcp_server_events import (
    MCP_SERVER_CREATED,
    MCP_SERVER_DELETED,
    MCP_SERVER_UPDATED,
    build_mcp_server_created_event,
    build_mcp_server_deleted_event,
    build_mcp_server_updated_event,
)
from app.events.system_prompt_events import (
    SYSTEM_PROMPT_CREATED,
    SYSTEM_PROMPT_DELETED,
    SYSTEM_PROMPT_UPDATED,
    build_system_prompt_created_event,
    build_system_prompt_deleted_event,
    build_system_prompt_updated_event,
)

__all__ = [
    "CONTEXT_SOURCE_CREATED",
    "CONTEXT_SOURCE_DELETED",
    "CONTEXT_SOURCE_UPDATED",
    "build_context_source_created_event",
    "build_context_source_deleted_event",
    "build_context_source_updated_event",
    "CREDENTIAL_CREATED",
    "build_credential_created_event",
    "MCP_SERVER_CREATED",
    "MCP_SERVER_DELETED",
    "MCP_SERVER_UPDATED",
    "build_mcp_server_created_event",
    "build_mcp_server_deleted_event",
    "build_mcp_server_updated_event",
    "SYSTEM_PROMPT_CREATED",
    "SYSTEM_PROMPT_DELETED",
    "SYSTEM_PROMPT_UPDATED",
    "build_system_prompt_created_event",
    "build_system_prompt_deleted_event",
    "build_system_prompt_updated_event",
]
