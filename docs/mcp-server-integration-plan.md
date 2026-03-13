# External MCP Integration Plan for Conversa

## Objective

Enable Conversa to register external MCP servers and let the current LLM execute their tools on behalf of the end user.

Initial target server:

- `linden` -> `https://api.mylinden.family/mcp`

Authentication requirement:

- MCP servers may use different auth requirements (none, bearer token, api key, basic auth, delegated exchange, and future mechanisms).
- Conversa should resolve auth per server through `credential_id` + `Credential.type`.
- For delegated user auth flows, obtain token with `exchange_token()` from `tessera_sdk.identies.client.IdentiesClient`.

## Current State (Relevant to This Plan)

- Conversa already resolves the linked internal user for Telegram messages through `Linker` and passes `user_id` into routing/session flow.
- LLM tool support exists today in `LLMRunner` with static local tools.
- `fastmcp` is already a project dependency.
- Redis-backed caching already exists in the codebase (via `tessera_sdk.utils.cache.Cache`), so we can reuse existing cache patterns.

## Recommended Architecture

### 1) MCP Server Registry (persistent)

Create a dedicated registry model/table (do not overload context sources):

- `id` (UUID)
- `server_id` (unique slug, e.g. `linden`)
- `name`
- `url` (MCP endpoint)
- `enabled` (bool)
- `credential_id` (optional FK -> `credentials.id`)
- `tool_prefix` (optional; default to `server_id`)
- `tool_cache_ttl_seconds` (default 300)
- `metadata` (JSONB for future transport options)
- audit fields/timestamps/soft-delete aligned with existing patterns

Add CRUD service + router for admin registration and updates.

Auth is credential-driven:

- `credential_id = NULL`: no auth header
- `credential_id != NULL`: resolve behavior from `Credential.type`
- for delegated user auth, add a credential type such as `delegated_identies_exchange` with fields:
  - `audience`
  - `scopes`

### 2) Credential-Based Auth Resolver

Introduce `MCPAuthResolverService`:

- input: `credential_id`, `user_id`, request context
- output: headers to attach to MCP client/requests
- behavior by credential type:
  - `None` -> no auth headers
  - `bearer_auth` / `api_key` / `basic_auth` -> use existing credential fields
  - `delegated_identies_exchange` -> call delegated token provider

Introduce `MCPDelegatedTokenRepository` (used only for delegated credential type):

- input: `user_id`, delegated credential fields (`audience`, `scopes`), request context
- calls `IdentiesClient.exchange_token(...)`
- returns bearer token + expiration

Token cache (short-lived):

- key: `mcp:token:{user_id}:{audience}:{scope_hash}`
- value: token + `exp`
- refresh when token is near expiry (e.g. `<60s`)
- on MCP `401`, force refresh and retry once

### 3) FastMCP Client Factory

Introduce `MCPClientFactory`:

- resolves registry entry
- resolves auth strategy from `credential_id` and credential type
- requests delegated token only when credential type requires exchange
- builds `fastmcp.Client` for remote URL transport with auth headers
- wraps `async with Client(...)` lifecycle

Implementation note:

- Keep client lifecycle request-scoped first (safe baseline).
- Add connection pooling/reuse only after metrics show the need.

### 4) Tool Catalog + Execution Layer

Introduce `MCPToolCatalogRepository`:

- fetch tools with `list_tools()`
- normalize to internal schema:
  - `qualified_name` (e.g. `linden__tool_name`)
  - `original_name`
  - `description`
  - `input_schema`
  - `server_id`

Introduce `MCPToolExecutor`:

- executes `call_tool(original_name, args)` against chosen server
- enforces timeout, retries (idempotent-safe), structured error mapping

### 5) LLM Integration Adapter

Add an adapter that converts catalog tools into LLM-callable tool definitions at request time.

Flow per user request:
 
1. Resolve user (`user_id`) from existing channel/linking flow.
2. Resolve enabled MCP servers for that tenant/env.
3. Load tool catalog (cached).
4. Provide adapted tools to the LLM runtime.
5. On tool call, execute through `MCPToolExecutor` using headers resolved by `MCPAuthResolverService`.
6. Return structured tool output to model.

Because tools are dynamic, prefer building the LLM tool set per request/session from cached catalog data.

## Caching Strategy (Recommended)

Cache **tool metadata** (catalog), not tool results.

### Cache key

Use:

- `server_id`

Example:

- `mcp:tools:{server_id}`

### TTL + invalidation policy

Use hybrid strategy:

- default TTL: `300s` (5 min)
- stale-while-revalidate: serve stale for up to `60s` while refreshing in background
- negative cache on transient failures: `30s`

Invalidate immediately when:

- server config changes (URL/credential_id/enabled)
- manual admin refresh endpoint is called
- MCP returns `tool not found` for a cached tool

Refresh triggers:

- cache miss
- stale entry
- forced invalidate

Why this strategy:

- avoids expensive `list_tools()` on every request
- limits stale tool windows
- remains robust when remote servers change without notifications

## Auth and User Identity Flow

For Telegram-originated requests:

1. Telegram user is linked to internal Conversa user (already in place).
2. Resolve server `credential_id`:
   - if delegated exchange type: call `exchange_token` with internal `user_id`
   - if static credential type: apply credential by existing credential service behavior
   - if null: send request without auth
3. Send final auth headers to MCP server.

Recommended `exchange_token` context payload:

- `channel` (e.g. `telegram`)
- `external_sender_id`
- `session_id`
- `request_id` / trace id
- `mcp_server_id`

This improves auditability and incident troubleshooting.

## Security and Guardrails

- Allowlist MCP base URLs (registry-level validation; HTTPS only).
- Enforce per-tool execution timeout (e.g. 15-30s default).
- Log tool invocations with redaction for sensitive arguments.
- Limit maximum tool calls per model turn (prevent loops/cost spikes).
- Prefix tool names by server to avoid collisions.
- Defer circuit breaker implementation to the hardening phase to keep initial delivery simple.

## Observability

Add metrics:

- `mcp_tool_catalog_cache_hit_total{server_id}`
- `mcp_tool_catalog_refresh_total{server_id,status}`
- `mcp_tool_call_total{server_id,tool,status}`
- `mcp_tool_call_latency_ms{server_id,tool}`
- `mcp_auth_resolve_total{credential_type,status}`
- `mcp_token_exchange_total{audience,status}` (delegated type only)
- `mcp_token_cache_hit_total{audience}` (delegated type only)

Structured logs:

- include `user_id`, `session_id`, `server_id`, `tool_name`, `request_id`.

## Phased Implementation Plan

### Phase 1 - Registry + Token Service

- Add `mcp_servers` model + migration.
- Add service/router for CRUD registration.
- Implement auth resolver using existing credential service behavior.
- Add new credential type for delegated exchange (`audience`, `scopes`).
- Implement delegated token service using `exchange_token`.
- Add token cache + retry-on-401 behavior for delegated type.

Deliverable:

- We can register MCP servers with mixed auth modes and execute them through credential-driven auth.

### Phase 2 - FastMCP Client + Tool Catalog

- Implement client factory.
- Implement `list_tools()` catalog loader/normalizer.
- Add Redis-backed catalog cache with TTL + invalidate.
- Add manual refresh endpoint (`POST /mcp-servers/{id}/refresh-tools`).

Deliverable:

- Catalog can be fetched/cached/refreshed for `linden`.

### Phase 3 - LLM Tool Execution Integration

- Add adapter between catalog tools and LLM runtime.
- Add executor path from tool call -> FastMCP `call_tool`.
- Persist tool-call events into session metadata/history as needed.

Deliverable:

- LLM can call `linden` tools during conversation.

### Phase 4 - Hardening + Rollout

- Add metrics/logging/circuit breaker.
- Add guardrails (timeouts, max calls/turn, fail-fast behavior).
- Add integration tests with mocked MCP server.
- Progressive rollout flag (off by default, then enable for Telegram only, then broader).

Circuit breaker scope for this phase (per `server_id`):

- State model: `closed` (normal), `open` (temporarily block), `half_open` (limited probes).
- Open when either threshold is reached in a rolling 60s window:
  - at least 5 consecutive failures, or
  - failure rate >= 50% with minimum 10 calls.
- Treat timeout/connection errors/HTTP 5xx as failures.
- While open, fail fast for cooldown (e.g. 30s).
- After cooldown, allow 1-2 probe calls; close on success, reopen on failure.
- Return a structured "tool temporarily unavailable" response while breaker is open.

Deliverable:

- Production-safe rollout with observability and rollback path.

## Test Plan

Unit tests:

- token caching/refresh logic
- catalog cache keying + TTL behavior
- invalidation triggers
- tool name normalization/collision handling

Integration tests:

- mocked MCP server for `list_tools` and `call_tool`
- no-auth server call works
- static bearer/api-key auth headers are injected correctly
- delegated token injected and validated
- 401 -> refresh token -> retry success
- tool missing after cache -> invalidate + refetch

E2E:

- Telegram linked user sends message that triggers MCP tool call
- response returns correctly and is stored in session history

## Recommended Defaults for First Release

- `tool_cache_ttl_seconds = 300`
- `stale_while_revalidate_seconds = 60`
- `tool_timeout_seconds = 20`
- `max_tool_calls_per_turn = 4`
- token refresh margin: 60 seconds before expiry

## Open Decisions to Confirm

- Single global MCP registry or tenant-scoped registry?
- Do we need to expose resources/prompts now, or tools-only for v1?
- Should tool invocation traces be shown in admin UI, API only, or both?

## First Server Bootstrap (Linden)

Initial registry payload proposal:

- `server_id`: `linden`
- `name`: `Linden MCP`
- `url`: `https://api.mylinden.family/mcp`
- `credential_id`: `<credential-id-for-delegated-identies-exchange>` (optional; nullable)
- `enabled`: `true`
- `tool_prefix`: `linden`


##  Future

Enabled MCP Servers should be cache same with tools