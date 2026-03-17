# RFC 001: Split CredentialRepository — CRUD vs Auth Application

**Status:** Implemented
**Date:** 2026-03-30

## Problem

`CredentialRepository` carried two unrelated responsibilities and two structural defects:

1. **Mixed concerns.** The class was both a DB repository (CRUD over `Credential` records) and an auth service (applying credentials as HTTP headers). 8 of its 11 call sites only performed CRUD, yet every instantiation paid the cost of initializing auth machinery.

2. **Eager construction of `MCPDelegatedTokenRepository`.** The `__init__` unconditionally constructed a `MCPDelegatedTokenRepository`, which allocates a `Cache` object and captures an M2M token provider closure — even in code paths that never performed delegated token exchange.

3. **No lazy M2M token acquisition.** The M2M token provider was wired up at construction time. Any path that triggered `_get_default_m2m_token` paid a blocking SDK call (`M2MTokenClient().get_token_sync()`) even when the credential type in use was static (bearer, basic, api_key).

4. **Inline strategy dispatch.** `_apply_credential_type` was a single method branching over all 5 credential types, mixing validation, transformation, and external calls. Adding a type required modifying the class.

## Decision

Split `CredentialRepository` into two classes:

- **`CredentialRepository`** — pure CRUD. `__init__(self, db: Session)`. No auth imports, no SDK dependencies, no optional collaborators.
- **`CredentialApplier`** — auth header injection. Owns all auth logic with lazy initialization of expensive collaborators.

Auth callers construct both; CRUD-only callers construct only `CredentialRepository`.

## Design

### `CredentialRepository` (after)

```python
class CredentialRepository(SoftDeleteRepository[Credential]):
    def __init__(self, db: Session) -> None: ...
    # CRUD methods only: get_credential, get_credentials, create_credential,
    # update_credential, delete_credential, get_credential_fields, to_credential_read, search
```

No references to `MCPDelegatedTokenRepository`, `CredentialType`, or tessera SDK.

### `CredentialApplier`

```python
class CredentialApplier:
    def __init__(
        self,
        db: Session,
        *,
        m2m_token_provider: Optional[Callable[[], Optional[str]]] = None,
        delegated_token_repo: Optional[MCPDelegatedTokenRepository] = None,
    ) -> None: ...

    def apply(
        self,
        credential_id: Optional[UUID],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """None credential_id → inject default M2M Bearer token (sync worker path)."""

    def apply_for_user(
        self,
        credential_id: Optional[UUID],
        *,
        user_id: Optional[UUID] = None,
        headers: Optional[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, str]:
        """None credential_id → return headers unchanged (MCP tool executor path)."""
```

Two named methods replace the previous `apply_credentials` / `apply_credentials_with_context` pair. The semantic difference (what `None` means) is encoded in the method name rather than a boolean flag.

### Lazy initialization

`CredentialApplier.__init__` stores overrides and sets two `None` sentinels:

```
self._m2m_token_provider → None until first M2M/delegated auth path
self._delegated_token_repo → None until first DELEGATED_IDENTIES_EXCHANGE path
```

`MCPDelegatedTokenRepository` is constructed at most once per `CredentialApplier` instance, and only when a delegated exchange actually executes. The tessera SDK import (`M2MTokenClient`) remains deferred inside the default provider function body.

### Lazy initialization chain

```
CredentialApplier(db)
  └─ CredentialRepository(db)     [pure DB, zero network]
  └─ _m2m_token_provider = None   [sentinel]
  └─ _delegated_token_repo = None [sentinel]

apply() or apply_for_user() called with BEARER/BASIC/API_KEY:
  └─ no lazy accessors touched

apply*() called with M2M_IDENTIES:
  └─ _get_m2m_token_provider() → assigns sentinel, returns callable
  └─ callable() → imports tessera_sdk, calls M2MTokenClient().get_token_sync()

apply*() called with DELEGATED_IDENTIES_EXCHANGE:
  └─ _get_delegated_token_repo() → assigns sentinel, constructs MCPDelegatedTokenRepository
       └─ MCPDelegatedTokenRepository.__init__ → allocates Cache()
       └─ m2m_token_provider → only called on cache miss
```

## Call Site Changes

| File | Change |
|---|---|
| `app/adapters/context_pack_fetcher.py` | Accept `CredentialApplier`; call `applier.apply(...)` |
| `app/commands/sync_context_for_user_command.py` | Pass `CredentialApplier(self.db)` to `ContextPackFetcher` |
| `app/mcp/tool_executor.py` | Use `CredentialApplier`; call `applier.apply_for_user(...)` |
| `app/repositories/mcp_tool_catalog_repository.py` | Use `CredentialApplier`; call `applier.apply_for_user(...)` |
| `app/commands/mcp_servers/refresh_mcp_server_tools_command.py` | Use `CredentialApplier`; call `applier.apply_for_user(...)` |
| `app/routers/credentials_router.py` | No change — CRUD only |

## Test Changes

Auth tests migrated from `tests/app/repositories/test_credential_repository.py` to a new file `tests/app/repositories/test_credential_applier.py`. CRUD tests remain in the original file with no changes, and no longer require mocking auth collaborators.

## Trade-offs

**Gained:**
- CRUD-only instantiations are zero-cost (no SDK imports, no cache allocation, no closures).
- Auth tests are independent of DB fixtures; CRUD tests are independent of token mocking.
- Adding a 6th credential type touches only `CredentialApplier._dispatch`.
- M2M token and delegated repo are provably not constructed unless their code path runs.

**Accepted:**
- Four call sites require mechanical updates (import change + method rename).
- `ContextPackFetcher` constructor signature changes from `CredentialRepository` to `CredentialApplier`.
- `_dispatch` retains inline if/elif — appropriate for a stable 5-type enum; a full Strategy registry would add indirection without benefit here.
- Lazy sentinels are not thread-safe if `CredentialApplier` were shared across threads. It is request-scoped (new instance per request/command), so this is not a concern in practice.
