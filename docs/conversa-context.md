# Conversa User Context: Context Pack + Snapshot + Event-Driven Updates

## Summary
Conversa needs a reliable, low-latency way to provide LLMs with user context when interacting via external chat platforms (Telegram, WhatsApp, etc.). User data is primarily owned by Linden and may be distributed across multiple Linden domains (relationships, assets, documents, preferences). Conversa must remain product-agnostic and cannot depend on real-time fan-out calls into Linden for every message.

This design introduces a **Source Registry** in Conversa (Prometheus-style) plus a **Context Pack** contract that sources can implement. Linden (and other products/services) register as sources, and Conversa periodically pulls curated, versioned payloads from each source, then merges them into a single **Context Snapshot**. Chat-time reads come from Postgres. A hot cache will be added in a later phase. Event-driven updates via NATS will reduce staleness and sync cost in a future phase.

---

## Problem
### What we’re solving
At chat time, Conversa needs enough user context to:
- Personalize responses (names, language/locale, preferences).
- Ground answers in known facts (relationships, important dates, key records).
- Avoid repeatedly asking the user for information we already have.

However, Linden’s data is:
- **Owned elsewhere** (Linden is source of truth for most user data).
- **Spread across domains** (different endpoints/models, sometimes different services).
- **Not optimized for chat-time** (fan-out calls are slow, brittle, and expensive).

### Constraints
- Conversa is a **generic gateway service** and must not embed Linden-specific business logic.
- Context does **not** need to be real-time, but must be “fresh enough” for a good experience.
- Chat-time must be **low latency** and resilient to partial upstream failure.
- Each source is responsible for the data it sends; Conversa does not validate the sensitivity or appropriateness of incoming payloads.

### Failure modes we must avoid
- Chat-time fan-out → increased latency, cascading failures, rate-limit issues.
- Unbounded context growth → prompt bloat, cost spikes, token limits.
- Schema drift without versioning → silently broken prompts.

---

## Goals
- Provide Conversa with a **single read** at chat-time to fetch user context.
- Keep Conversa **product-agnostic** via a stable, versioned contract.
- Support **stale-tolerant** behavior with clear freshness guarantees.
- Enable incremental improvement: start with periodic sync, later move to event-driven updates.

## Non-goals
- Perfect real-time synchronization.
- A universal “profile system” for all products (this can evolve later).
- Replacing Linden’s canonical data stores.

---

## Source Registry (Prometheus-style)
Conversa must support user context that is **spread across multiple services** (Linden + future products). To keep Conversa generic and avoid hard-coding integrations, Conversa maintains a **Source Registry**: sources are registered with connection details and declared capabilities, and Conversa pulls context packs from those sources on a schedule (and later via events).

### What is a “source”
A **source** is any service that can produce a context payload for Conversa, typically by implementing a `context-pack` endpoint or exposing a compatible adapter.

Examples:
- `linden-api` (relationships, records)
- `vaulta` (user files metadata)
- `custos` (roles/permissions summary)

### Source registry responsibilities
- Store source connection configuration (base URL, auth mode, scopes).
- Define refresh policy (poll interval, backoff).
- Define merge policy/priority when multiple sources provide the same field.

### Minimal source configuration
Each registered source has:
- `source_id` (stable identifier)
- `display_name`
- `base_url`
- `auth` (M2M token, API key, etc.). Default to TesseraSDK M2M token.
- `capabilities`:
  - `supports_etag`: `true|false`
  - `supports_since_cursor`: `true|false`
- `poll_interval_seconds`
- `enabled`

### Data model (Conversa)
**Table: `context_sources`**
- `id` (uuid)
- `source_id` (text, unique) — e.g., `linden-api`
- `display_name` (text)
- `base_url` (text)
- `auth_config` (jsonb) — encrypted/secret-managed where appropriate
- `capabilities` (jsonb)
- `poll_interval_seconds` (int)
- `enabled` (bool)
- `created_at` / `updated_at` / `deleted_at`

**Table: `context_source_state`** (per source + user)
- `id` (uuid)
- `source_id` (fk)
- `user_id` (uuid) — Tessera user UUID from the users table
- `last_success_at` (timestamptz)
- `last_attempt_at` (timestamptz)
- `last_error` (text)
- `etag` (text, nullable)
- `since_cursor` (text, nullable)
- `next_run_at` (timestamptz)

### Operational guardrails
- Per-source rate limiting.
- Per-user debounce (avoid refresh storms).
- Exponential backoff on repeated failures.
- Safe defaults: if a source is failing, continue using last known good snapshot.

## Proposed solution (phased)

### Phase 1: Context Pack contract (implemented by Linden and other sources)
Each registered source can expose a **Context Pack** endpoint (or adapter) that returns an assistant-oriented snapshot of relevant fields for a user. Linden is the first implementation.

**Key properties**
- **Curated**: allowlisted fields only (PII minimization).
- **Versioned**: explicit schema version and source versions.
- **Audience-scoped**: payload tailored for `conversa`.
- **User-scoped**: sync is by user ID; once a user is linked (in the users table in Conversa), the sync process can start.

**Suggested endpoint (per source)**
- `GET /v1/context-pack`

**Required query parameters**
- `user_id`: UUID (Tessera user ID)
- `audience`: fixed value `conversa`

**Optional query parameters**
- `since`: optional cursor (enables incremental sync)

**Response**
- Must include `schema_version`, `generated_at`, and `source` identifiers.
- Should include optional `etag` / `cursor`.

**Response (example shape)**
```json
{
  "schema_version": "1.0",
  "generated_at": "2026-02-16T21:30:00Z",
  "audience": "conversa",
  "subject": {
    "type": "user",
    "id": "usr_uuid_123"
  },
  "sources": {
    "linden": {"source_id": "linden-api", "version": "2026.02.16", "etag": "..."}
  },
  "facts": {
    "display_name": "Emi",
    "locale": "es-ES",
    "timezone": "Europe/Madrid",
    "preferences": {
      "tone": "direct",
      "units": "metric"
    }
  },
  "recents": {
    "top_entities": [
      {"type": "dependent", "id": "dep_1", "label": "Child", "url": "https://xxxx.com/dep1"},
      {"type": "document", "id": "doc_9", "label": "Will", "url": "https://xxxx.com/documents/doc_9"}
    ]
  },
  "pointers": {
    "documents": ["doc_9", "doc_10"],
    "records": ["rec_1"]
  }
}
```

**Notes**
- `facts` must remain **small and structured**. Use IDs/pointers for larger content.
- For RAG/retrieval: Linden (or any source) will expose an MCP that the LLM can use to interact with sources. This is not yet implemented in Tessera.

## Field semantics and examples (`facts`, `recents`, `pointers`)

This section defines what belongs in each field, what must not be included, and concrete examples.

### `facts` — prompt-ready, small, stable
**Purpose**
- Small, structured fields safe to include in every prompt.
- Stable across requests; low churn.

**Include**
- Display attributes (name, locale, timezone).
- Booleans/enums and small preference summaries.
- Derived/abstracted facts (e.g., `has_dependents: true`).

**Do NOT include**
- Large text blobs, histories, documents.
- Raw sensitive content unless strictly required.
- Unbounded lists.

**Example**
```json
"facts": {
  "display_name": "Emi",
  "locale": "es-ES",
  "timezone": "Europe/Madrid",
  "has_dependents": true,
  "preferences": { "tone": "direct", "units": "metric" }
}
```

### `recents` — short-lived relevance hints
**Purpose**
- Lightweight signals about what is top-of-mind for the user.
- Guides relevance without bloating context.

**Include**
- Recently touched entities or topics (IDs + labels).
- Small labels or URLs for UX linking.

**Do NOT include**
- Full histories or logs.
- Large payloads or PII-heavy content.

**Example**
```json
"recents": {
  "top_entities": [
    { "type": "dependent", "id": "dep_1", "label": "Child" },
    { "type": "document", "id": "doc_9", "label": "Will" }
  ],
  "recent_topics": ["benefits", "documents"]
}
```

### `pointers` — references for on-demand retrieval (MCP-ready)
**Purpose**
- Reference large or sensitive data without embedding it in prompts.
- IDs can be used by the LLM via MCP (Linden/sources expose MCP; not yet implemented in Tessera).

**Include**
- IDs/handles for documents, records, entities.
- Content must be IDs only.

**Do NOT include**
- Any document content, balances, notes, or PII.
- Display text beyond minimal labels in `recents`.

**Examples**
```json
"pointers": {
  "documents": ["doc_9", "doc_10"],
  "records": ["rec_1"]
}
```
**Pointers boundedness (simple approach)**
- Cap each pointer list at a fixed max count (e.g. 100 IDs per pointer category). Trim or truncate when merging. This keeps the merged snapshot bounded without complex pagination.

### Validation rules (enforced by Conversa)
- `facts` must remain bounded in size (hard cap in bytes).
- `recents` must be capped in count (e.g., top N entities).
- `pointers` must contain IDs only; no content blobs. Apply a max count per pointer category (e.g. 100).
### Merging multiple sources
When multiple sources provide context for the same user, Conversa produces a single **merged snapshot**.

#### Principles
- Conversa does not attempt to understand product semantics; it merges using explicit rules.
- Sources must publish **structured facts** (small) and **pointers** (IDs/refs) rather than large blobs.
- The merged snapshot must remain bounded in size.

#### Merge strategies
For each field/key in the merged model, choose one of:
- **Priority winner** (default): highest-priority source wins.
- **Freshest winner**: the value with the newest `generated_at` wins.
- **Union**: merge lists/sets with de-duplication (use stable IDs).
- **Namespace**: keep source-scoped values under `by_source.{source_id}` when no single truth exists.

#### Priority configuration
Use the simplest approach for now: a single merge rule (e.g. **priority winner** only). Store as static config (e.g. YAML or env). Example: `linden-api` has highest priority for `facts.display_name`; `pointers.documents` uses union across sources.

#### Conflict reporting
When two sources disagree on a priority field:
- Keep the winner.
- Record a lightweight conflict entry in logs/metrics (do not store sensitive values).

---

### Phase 2: Conversa stores Context Packs as snapshots
Conversa periodically fetches context packs from all enabled registered sources, merges them, and stores the resulting snapshot in **Postgres** (durable snapshot storage, auditability, history/rollbacks). A hot cache will be added in a later phase.

#### Data model (Conversa)
**Table: `context_snapshots`**
- `id` (uuid)
- `user_id` (uuid) — Tessera user ID
- `schema_version` (text)
- `generated_at` (timestamptz)
- `payload` (jsonb)
- `payload_hash` (text) — optional dedupe
- `created_at` (timestamptz)

**Indexes**
- `(user_id, generated_at desc)`
- `(user_id, schema_version)`

#### Cache (to be added later)
A hot cache layer (e.g. Redis) will be introduced in a future phase to reduce Postgres read load at chat-time. Until then, reads go directly to Postgres. When a cache is added, the next chat after a sync should see the new snapshot immediately (cache populated or invalidated on sync completion).

#### Read path (chat-time)
1. Load latest snapshot from Postgres by `user_id`.
2. If found: use it.
3. If not found: proceed with minimal context and enqueue a sync.

#### Integration point
Context is built in the routing layer (`app/core/routing.py`), after `get_or_create_session` and before `llm.run`. Fetch the snapshot for the session's `user_id`, then pass it to `llm.run(msg, history=history, context=context)`.

#### Write path (sync)
- Background job enumerates enabled `context_sources` and linked users (from `users` table).
- For each source + user:
  - Call `/v1/context-pack` with `user_id`, `audience=conversa`.
  - Use `If-None-Match` when `etag` is available. On 304 Not Modified: skip storing, update `next_run_at` only.
  - Validate `schema_version` and required fields.
  - Persist per-source state (`etag`, `cursor`, timestamps, errors).
- Merge all successful source packs into a single merged payload.
- Store merged payload in Postgres.

---

### Phase 3: Event-driven updates via NATS (later)
Periodic sync is simple but can be wasteful and stale. We add NATS events to refresh only what changed.

**Notes / gaps (to be addressed in future phase)**
- Subject naming alignment: current Conversa config uses `nats_subjects: com.mylinden.>` and `nats_stream_name: EVT_LINDEN`. Phase 3 example topics (e.g. `linden.user.updated`) may need to align with this (e.g. `com.mylinden.linden.user.updated`). Clarify convention.
- User vs account in event payload: sync is user-scoped; ensure event `subject` uses `user_id` consistently.
- Queue group and stream configuration for context-refresh consumers.

#### Event approach (draft)
Linden publishes events whenever context-relevant fields change. Conversa subscribes and refreshes affected users.

**Topics (example, naming TBD)**
- `linden.user.updated`
- `linden.dependent.updated`
- `linden.document.added`
- `linden.document.updated`

**Event payload (minimal)**
```json
{
  "event_id": "evt_...",
  "event_type": "linden.user.updated",
  "occurred_at": "2026-02-16T21:35:00Z",
  "subject": {"type": "user", "id": "usr_uuid_123"},
  "changed": ["preferences", "relationships"],
  "cursor": "..."
}
```

#### Consumer behavior (Conversa)
- On event: enqueue a refresh job for the referenced user.
- Debounce per user (e.g., coalesce multiple events within 30–60s).
- Refresh by calling the same `/v1/context-pack` endpoint.

#### Why we still fetch the pack
- Keeps Conversa generic.
- Avoids making Conversa interpret many domain event schemas.
- Linden remains responsible for producing the curated assistant payload.

---

## API contract details (Linden → Conversa)
### Versioning
- `schema_version` is required.
- Backward-compatible additions are allowed within a major version.
- Breaking changes require a major version bump.
- Conversa must reject unknown major versions and fall back gracefully.

### Safety & privacy
- Context Pack must be **allowlist-based**.
- Avoid raw sensitive data unless strictly required.
- Prefer derived/abstracted facts (e.g., “has_dependents=true” rather than full details).

### Authorization
- The Context Pack endpoint must enforce that only authorized callers can fetch data.
- Recommended: service-to-service auth (M2M) with explicit audience/scope for `conversa`.
- The endpoint must scope context to the requested user and ensure Conversa only fetches what the user is entitled to.

---

## Operational considerations
### Observability
- Metrics:
  - `context_snapshot_age_seconds`
  - `context_sync_success_rate`
  - `context_sync_latency_ms`
  - `context_pack_payload_bytes`
- Logs:
  - user identifiers, schema version, etag, refresh decisions
- Tracing:
  - trace the sync fetch and DB writes

### Rate limiting & backoff
- Apply per-user debouncing.
- Exponential backoff on source errors.
- Circuit-breaker behavior: if a source is down, continue with last known good snapshot.

### 304 / If-None-Match behavior
- When `etag` is available, send `If-None-Match: <etag>` on context-pack requests.
- On 304 Not Modified: skip storing a new snapshot, update `next_run_at` and `last_success_at` only. No payload transfer.

### Failure-mode strategy for partial/invalid data
- If Context Pack is missing required fields or schema major is unsupported:
  - Do not overwrite last known good snapshot.
  - Emit an error metric/log.
  - Fall back to minimal context for the current chat.
- If only *some* optional fields are missing:
  - Accept and store the pack, but track missing fields in logs/metrics.

---

## Implementation plan

* Framework conventions
  * Follow existing Conversa Python/FastAPI patterns (project layout, dependency injection, routers, background workers, error handling).
  * Reuse shared utilities and middleware; do not introduce parallel patterns.

* API design
  * Pydantic models for request/response schemas.
  * Typed interfaces for source adapters.
  * Consistent error models and status codes with existing Conversa endpoints.

* Object-oriented design
  * Use explicit interfaces/abstract base classes for:
    * Sources/adapters
    * Merge strategies
    * Fetch/sync strategies
  * Prefer composition over inheritance.
  * Single-responsibility for services (fetch, merge, validate).

* Extensibility
  * New sources must implement a common adapter interface.
  * Merge rules must be pluggable/config-driven, not hard-coded.

* Testing
  * Unit tests for merge rules and adapters.
  * Contract tests for /v1/context-pack.
  * Integration tests for Postgres read/write paths.

### Engineering standards (Conversa)

### Phase 1 (Linden)
- Add `/v1/context-pack` endpoint.
- Define `schema_version=1.0` payload with allowlisted facts.
- Implement authorization/scoping for `audience=conversa`.

### Phase 2 (Conversa)
- Add `context_snapshots` table.
- Add sync worker (polling).
- Integrate chat-time lookup in routing (Postgres → minimal context); pass context to `llm.run`.
- Add metrics/logs.

### Phase 3 (NATS)
- Define Linden event topics and minimal event payload.
- Add Conversa subscriber + debounce queue.
- Switch from pure polling to hybrid: events-triggered refresh + periodic safety sync.

---

## Open questions
- How are sources registered/managed (admin UI vs config file), and how are secrets stored (vault, env, KMS)?
- What is the initial set of merge rules and per-field priorities, and who owns those decisions (product vs platform)?
- Exact allowlist fields for `facts` (needs product input).
- Whether Linden provides `etag`/`If-None-Match` support to reduce payload transfer.