## Problem Statement

Conversa periodically syncs per-user context from every enabled context source and stores a merged snapshot that's read at chat time (see `docs/context-sources-sync.md`). None of that sync activity is visible today: `ContextSourceState` (per `(source, user)` sync bookkeeping — `last_success_at`, `last_error`, `next_run_at`, `etag`) has no API and no UI. When a user's chat replies look uninformed ("why doesn't this user have context?"), the only way to answer that is to query the database directly.

As the operator running Conversa, we want to open a context source in `conversa-portal` and see, per user, whether it has successfully synced, when it last tried, and what the error was if it didn't — without shelling into Postgres.

## Solution

Add a read-only "Sync State" view, scoped to a single context source, to both `conversa` (new API) and `conversa-portal` (new tab):

- A new `GET /context-sources/{id}/sync-state` endpoint on the existing `context_source` RBAC resource, returning paginated `ContextSourceState` rows for that source, joined with the user's email for a readable label, optionally filtered by a search term (email substring or exact user ID).
- A new "Sync State" tab on the Context Source details page in `conversa-portal`, alongside the existing "Overview" tab, showing a searchable table of that data.
- A "Re-sync" action per row, reusing the existing (already-implemented, currently unused-by-any-UI) `POST /context-sources/sync/{user_id}` endpoint — no new backend work needed for this part.

This is explicitly scoped to `ContextSourceState` only. The merged `ContextSnapshot` payload is deliberately **not** surfaced here — see Out of Scope.

## User Stories

1. As an operator, I want to open a context source and see a list of users with their sync status, so that I can spot who's failing or stale without a database query.
2. As an operator, I want to search that list by a user's email, so that I can jump straight to the one user I'm debugging.
3. As an operator, I want to see the last error message for a user/source pair, so that I know why a sync is failing (bad credential, upstream 500, timeout, etc.) without reading logs.
4. As an operator, I want to see `next_run_at`, so that I know whether a stale-looking user is about to retry on its own or is stuck.
5. As an operator, I want to trigger an immediate re-sync for a user directly from this view, so that I can unblock them without waiting for `next_run_at` or reaching for `curl`.
6. As an operator, I want a user who has never synced (no state row yet) to show up clearly as "not yet synced" rather than being silently absent from the list, so that I can distinguish "still pending" from "broken."
7. As a developer maintaining Conversa, I want this endpoint to reuse the existing RBAC resource (`context_source`) rather than introduce a new one, so that permission management doesn't fragment further for what is just a read-only view of existing data.
8. As a developer maintaining Conversa, I want the sync-state query to be a single indexed, source-scoped query (not the due-pairs task's in-memory double loop over all sources × all users), so that this view stays fast regardless of platform size.
9. As a security-conscious operator, I want this view to expose sync bookkeeping only — not the actual merged context content (facts/recents/pointers) — so that a debugging screen doesn't become a new place PII leaks out.

## Implementation Decisions

**Backend (`conversa`)**

- New schema `app/schemas/context_source_state.py`: `ContextSourceStateRead` — `user_id: UUID`, `user_email: str | None`, `last_success_at`, `last_attempt_at`, `last_error`, `next_run_at`, `etag: str | None`. No snapshot data included.
- New repository method on `ContextSourceStateRepository` (or a small addition alongside it) that queries `ContextSourceState` filtered by `source_id`, left-joined to `User` for `email`, with an optional case-insensitive `search` filter matched against `User.email`, ordered by `last_attempt_at DESC NULLS LAST`. Returns a `Query` for `fastapi_pagination.ext.sqlalchemy.paginate`, following the same pattern `ContextSourceRepository.get_context_sources_query()` already uses.
- New endpoint on `context_sources_router.py`: `GET /context-sources/{id}/sync-state`, `response_model=Page[ContextSourceStateRead]`, gated by the existing `rbac["read"]` dependency for the `context_source` resource (same as `list_context_sources`) — no new RBAC resource. Path param reuses `get_context_source_by_id` to 404 on an unknown source before querying state.
- A user who has never had a sync attempt for this source has no `ContextSourceState` row at all (rows are created lazily via `get_or_create_state` the first time a sync runs for that user). These users simply won't appear in the query result. The portal surfaces this as "no sync state yet" only in the context of a search that returns zero rows for a known user — see the portal section below; this endpoint does not attempt a full cross-join of all platform users to backfill "never synced" rows, to avoid reintroducing the O(sources × users) scan pattern `get_due_user_source_pairs` already has.
- No changes to `SyncContextForUserCommand`, `ContextPackFetcher`, or the Celery tasks — this PRD is additive, read-only surface area on top of existing sync mechanics.

**Backend (re-sync action)**

- No new endpoint. The portal calls the existing `POST /context-sources/sync/{user_id}` (already gated by `rbac["update"]`, already synchronous — it runs `SyncContextForUserCommand.execute` inline and returns once done or failed).
- Note this endpoint syncs the user across **all enabled sources**, not just the one whose tab you're viewing — that's existing behavior, and the portal's re-sync button should be labeled accordingly (e.g. "Re-sync this user" rather than "Re-sync this source"), so operators aren't surprised other sources also get touched.

**Frontend (`conversa-portal`)**

- New route file `app/routes/main/context-sources/details/sync-state.tsx`, registered in `app/routes.ts` alongside the existing `overview` route under `:contextSourceID`.
- New tab entry added to the `menuItems` array in `app/routes/main/context-sources/details/layout.tsx` (currently only has "Overview"), pointing at `/context-sources/{id}/sync-state`.
- New resource layer: `app/resources/queries/context-sources/context-source-sync-state.queries.ts` (+ type/schema) following the same shape as the existing `context-source.queries.ts`, and a corresponding hook under `app/resources/hooks/context-sources/`.
- Table columns: user (email, falling back to a truncated `user_id` if email is null), last success, last attempt, last error (truncated, full text on hover/click), next run at, and a "Re-sync" button per row.
- A search input above the table, debounced, passed through as the `search` query param to the new endpoint.
- Re-sync button calls the existing sync mutation (new hook wrapping `POST /context-sources/sync/{user_id}`), shows a loading state while the request is in flight (it's synchronous and can take a few seconds per source), and invalidates/refetches the sync-state list on success so the row updates in place.

## Testing Decisions

- **Repository query**: test the new `ContextSourceState` query directly against a test DB — filtering by `source_id`, the `search` filter matching on email (case-insensitive, partial), and correct `NULLS LAST` ordering on `last_attempt_at`.
- **Router endpoint**: test `GET /context-sources/{id}/sync-state` for the pagination envelope shape, 404 on unknown source id, RBAC denial for a caller without `context_source:read`, and that a source with no state rows returns an empty page rather than an error.
- No new tests needed for the re-sync action itself — it's calling an existing, already-tested endpoint unchanged.
- Portal: basic coverage of the new tab consistent with how the existing "Overview" tab / `context-sources` list page are tested today, if the project has frontend tests in place for comparable pages.

## Out of Scope

- Any surfacing of the merged `ContextSnapshot` payload or its key names — the snapshot isn't scoped to a single source (see `docs/context-sources-sync.md`), so attaching it to a per-source tab would misrepresent it as this-source-only data. A future, explicitly user-scoped (not source-scoped) "user context viewer" is a separate PRD if this becomes needed.
- Per-source provenance (which source actually contributed which merged fact/key) — `ContextMergeRepository.merge_packs()` discards this today; capturing it would require a schema change to persist key-shape at fetch time, out of scope here.
- A source-centric health view (aggregate error rate, count of stale users per source) or a global sync activity/run log — both explicitly deferred to a later phase per the earlier design discussion.
- Backfilling "never synced" rows for every enabled user via a cross-join — the endpoint only returns users who already have a `ContextSourceState` row.
- Any change to sync cadence, retry/backoff behavior, or the Celery task/beat schedule.
- A dedicated new RBAC resource for this view — it rides on the existing `context_source` resource's `read`/`update` permissions.

## Further Notes

- Confirmed during design: `POST /context-sources/sync/{user_id}` already exists (`context_sources_router.py:59-76`) and is unused by any current UI — this PRD's re-sync button is pure frontend wiring plus a thin new hook, not new backend surface area.
- Confirmed during design: `ContextSnapshotRepository.get_latest_snapshot(user_id)` has no `source_id` parameter — snapshots are per-user, merged across all sources, not per `(source, user)`. This is why snapshot content is excluded from this source-scoped view rather than included "for extra visibility."
