# RFC 002: Async/Sync Deadlock in tessera_sdk RBAC Authorization Dependency

**Status:** Implemented  
**Date:** 2026-06-01

## Problem

Sending a message via Telegram causes a timeout cascade that silently drops the message with no response to the user.

### Observed symptoms

- `conversa` logs `TesseraError: [IdentiesClient] Request failed` after 3 seconds
- `identies` logs `ReadTimeout: HTTPConnectionPool(host='localhost', port=8002): Read timed out (read timeout=3)`
- `telegram.ext.Application` logs `No error handlers are registered, logging exception`

### Call chain

```
conversa (telegram message received)
  → linker.py: is_account_linked()
  → identies POST /external-accounts/check          [sync requests call, blocks event loop]
      → tessera_sdk authorize() dependency
      → custos POST /authorization/authorize         [sync requests call, blocks event loop]
          → custos AuthenticationMiddleware
          → identies GET /.well-known/jwks.json      [← identies is BLOCKED, can't respond]
          ↑ timeout (3s)
      ↑ timeout (3s)
  ↑ timeout (3s)
```

### Root cause

The `tessera_sdk` RBAC `authorize()` FastAPI dependency uses the synchronous `requests` library to call `custos /authorization/authorize`. Because `identies` is a FastAPI application running on a single-threaded asyncio event loop (one uvicorn worker), this synchronous HTTP call **occupies the event loop thread** for the duration of the request.

While `identies` is blocked waiting for `custos` to respond, `custos`'s `AuthenticationMiddleware` attempts to verify the inbound JWT by calling `identies GET /.well-known/jwks.json`. `identies` cannot respond to this JWKS request — its event loop is stuck on the blocking `requests` call to `custos`. Both services wait on each other until the 3-second SDK timeout fires, cascading back to `conversa`.

This is a classic event loop deadlock: a synchronous outbound call inside an async handler blocks the loop, preventing it from servicing an inbound request that the outbound call depends on.

### Why enforce() itself is not the bottleneck

`CasbinRepository` uses an `@lru_cache()` singleton and calls `enforcer.load_policy()` at initialization, so all policies are in memory. The `enforce()` call is pure in-memory and fast. The delay is entirely caused by the synchronous HTTP calls in middleware, not Casbin evaluation.

## Decision

Replace the synchronous `requests` calls in `tessera_sdk`'s `authorize()` dependency and base client with `httpx.AsyncClient`, so the event loop remains free to service inbound requests (including JWKS lookups) while outbound authorization calls are awaited.

As a secondary fix, add a `TesseraError` / `ReadTimeout` handler in the `conversa` Telegram plugin so users receive a visible error instead of a silent drop.

## Design

### 1. tessera_sdk: async base client

The `tessera_sdk/clients/_base/client.py` `_make_request` method must be converted from synchronous `requests.Session` to `httpx.AsyncClient`. All callers that are already in async context (FastAPI dependencies, middleware) will `await` the call naturally.

Services that call the SDK from sync context (e.g., Celery workers) should use `httpx.Client` via a separate sync variant or `asyncio.run()`.

### 2. identies: async RBAC dependency

`tessera_sdk/server/dependencies/authorization.py` must be an `async def` FastAPI dependency. The `authorize()` call inside it must be `await`ed so FastAPI yields control to the event loop while waiting for custos.

### 3. conversa: Telegram error handler

`conversa/app/channels/plugins/telegram/plugin.py` should register an error handler with `application.add_error_handler(...)` that catches `TesseraError` and `ReadTimeout` and sends a user-facing reply.

## Acceptance Criteria

- [ ] Sending a Telegram message to a linked account succeeds without timeout errors
- [ ] Sending a message while custos is slow (>1s) does not deadlock — identies remains responsive to JWKS requests
- [ ] A `TesseraError` during account linking sends a user-facing error message via Telegram instead of silently dropping
- [ ] Existing tests pass
