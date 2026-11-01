## Problem Statement

Conversa only syncs context for users it already knows about. The periodic sync (`sync_context_all_due_task`, see `docs/context-sources-sync.md`) enumerates rows in Conversa's `users` table and checks each one against the enabled context sources. A user with no row in that table is never synced.

A row gets into that table in one of two ways today:

- **Telegram (and other linked channels):** the user completes the Identies link flow. The linker then registers the user. Sync starts at the next Beat tick.
- **Chat assistant (`POST /chat/completions`):** these users are already known to Tessera, so they need no link. Their row is created on first contact, not when the account is created. Their first message finds no context snapshot, so it is answered without context, and a sync is queued for the next message (`app/core/routing.py`, `_load_context_for_user`).

For chat-assistant users, the first conversation is when context matters most, and today it is the moment the system first learns the user exists.

Identies publishes `user.created` with a full user projection body when a human is first onboarded (the first authenticated request through Identies' auth middleware, `app/middleware/auth/user_handler.py`), and when a service account or agent is created (`docs/user_events.md` in the identies repo). A human who has never hit Identies produces no event. Conversa's NATS worker already receives `com.identies.>` and passes every event to `process_nats_event_task`.

Two further problems:

- `get_due_user_source_pairs` loaded at most 200 sources and 1000 users. Users beyond the cap were never synced, and nothing reported it.
- Conversa had several copies of the Identies-to-local-user mapping, and the onboarding insert was not idempotent.

## Solution

Register users when Identies announces them, and check that a user exists before a chat is answered:

1. **Event listener.** Handle `com.identies.user.created` and `com.identies.user.updated`. Human users are upserted by Identies `id`. A created human gets its first context sync queued straight away.
2. **Chat existence check.** Before a chat API message creates a session, the user is looked up locally. If missing, Identies is asked. A user that is unknown to both is rejected with 403.
3. **One registration path.** A single `UserProvisioner` owns every local registration: the linked-account flow, the chat check, and the event listener. One `IdentiesUser` schema is the only mapping from Identies data to a local row.
4. **Uncapped due-pairs query.** `get_due_user_source_pairs` becomes one SQL query over enabled sources and users, with no 200 or 1000 limit.

Later phases (not in this change): a one-time backfill of existing Identies users, a periodic reconcile for events lost to NATS outages, and offboarding.

## User Stories

1. As a chat-assistant user, I want my context ready when I send my first message, so that the assistant already knows what it should know about me.
2. As an operator, I want every human user in Identies to be in Conversa's `users` table without anyone linking them first, so that the sync covers the whole platform.
3. As an operator, I want a user that Identies no longer knows to be rejected at chat, so that unknown principals cannot start conversations.
4. As a developer maintaining Conversa, I want user registration to be idempotent, so that a redelivered event or a repeated onboarding never fails on a duplicate key.
5. As a developer maintaining Conversa, I want every user and source considered by the sync, with no hidden cap, so that growth does not silently stop syncing users.
6. As an operator, I want to see in the existing "Conversa — Context sync" Grafana dashboard whether newly registered users are being synced, so that I can confirm the feature works in production.

## Implementation Decisions

**Identies data (`app/schemas/identies_user.py`)**

- `IdentiesUser` is the one parsed form of an Identies user, from the API or from an event. A missing `kind` means human. `is_human` is false for agents and service accounts.
- `to_onboard()` is the only mapping from Identies data to a local row.

**Directory (`app/services/identies_directory.py`)**

- `IdentiesDirectory` is a protocol with `get_user(user_id) -> IdentiesUser | None`. `IdentiesApiDirectory` implements it on top of `get_internal_user`. `IdentiesNotFoundError` maps to `None`. Other errors propagate.

**Provisioner (`app/services/user_provisioner.py`)**

- `ensure_user(user_id)`: returns the local user if it exists. Otherwise asks Identies and syncs the result. Returns `None` if Identies does not know the user, or if the local row is soft-deleted. A tombstone is never revived by a read.
- `sync(identies_user)`: upserts the local row.
- Identies is called outside any database transaction. Results are returned as schemas, so no caller holds an ORM row after its session ends.
- `UnknownUserError` is raised by the chat path. The exception registry maps it to 403.

**Repository (`UserRepository.upsert_user`)**

- Replaces `onboard_user`, which was a plain insert. `upsert_user` creates the row, or refreshes the existing row with the same id. It never revives a soft-deleted row.

**Event handling (`app/services/identies_user_events.py`)**

- `IdentiesUserEventHandler` handles `com.identies.user.created` and `com.identies.user.updated`. It skips non-human users, syncs humans, and queues `sync_context_for_user_task` on `created` only.
- Ordering: last write wins. The row's `updated_at` is set by Conversa, not Identies, so comparing it with the event's `updated_at` would skip real updates. Identies' own `updated_at` is not stored. Adding a column for it is a later decision.
- `user.deleted` is not handled. Identies only publishes it for service accounts and agents, which are skipped. Human offboarding, `com.identies.user.offboarding_scheduled`, is out of scope until its payload is verified.

**Chat path (`app/core/routing.py`)**

- `Router` takes an optional `users: UserProvisioner`. `_prepare_api_message` calls `ensure_user` in a thread before it creates a session, and raises `UnknownUserError` if the result is `None`.

**Due-pairs query (`app/repositories/context_source_state_repository.py`)**

- `get_due_user_source_pairs` is one `select` over `ContextSource` cross-joined with `User`, outer-joined to `ContextSourceState` on the pair. A pair is due when the source is enabled and either no state row exists or `next_run_at <= now`. Rows with an unset `next_run_at` are not due, as before.
- The constructor no longer takes source or user services. The only caller that passed them was updated.

**Other**

- `app/core/identies_client.py`: one builder for the Identies client, shared by the linker and the directory.
- The linker calls `UserProvisioner.ensure_user` instead of its own `_fetch_user`.
- **Error reporting (`app/infra/error_reporting.py`):** Celery workers report failed tasks to Rollbar through a `task_failure` handler, production only. Rollbar is initialized in each worker child process (`worker_process_init`). The API and the workers share `init_rollbar()`. This follows Looply's setup. A task that catches an exception and only logs it is not reported. The NATS worker (`run_nats_worker.py`) only dispatches tasks, so its failures are not reported directly. Beat runs no tasks and needs no Rollbar setup.

## Testing Decisions

- **Provisioner** (`tests/app/services/test_user_provisioner.py`): existing user returned without calling Identies; missing user registered once; unknown user returns `None`; soft-deleted user not revived and not fetched; repeated sync refreshes one row; agents flagged as service accounts.
- **Event handler** (`tests/app/services/test_identies_user_events.py`): created human registered and sync queued; updated human refreshed without a queued sync; agents and service accounts skipped; a missing `kind` treated as human; only the two registration event types handled.
- **Chat check** (`tests/app/core/test_routing.py`): an unknown user raises `UnknownUserError`. The existing routing tests use an autouse fixture so they never reach Identies.
- **Due-pairs query** (`tests/app/repositories/test_context_source_state_repository.py`): more than 1000 users and more than 200 sources are both returned. Both tests fail on the previous code (1000 and 200 returned). A state row with no `next_run_at` is not due.
- **End to end (staging, not automated):** publish a `user.created` event for a test human, then confirm a `users` row and a sync state row appear within a minute. Confirm the chat assistant returns context on that user's first message.

## Phase 2 Design: Backfill and Reconcile (deferred)

Current user count is about 20, so this is not urgent. The direction changed: Conversa will not call Identies' user list for backfill. The plan is to replay events instead.

- **Backfill by event replay:** Identies republishes `com.identies.user.created` and `com.identies.user.updated` for existing humans on NATS. Conversa consumes them with the existing listener. Conversa has no new dependency on Identies' API.
- **Consumer detail to handle:** the worker's JetStream subscription uses `DeliverPolicy.LAST` on a durable consumer (`run_nats_worker.py`). A replay of older messages will not reach it. Replay needs either a separate one-off consumer with `DeliverPolicy.ALL`, or Identies publishing the replay on a live subject. Decide this with the Identies owners before building it.
- **Reconcile:** deferred. The same republish could also cover events lost to NATS outages, which would remove the need for a periodic Conversa-side scan.
- **Filtering:** unchanged. Agents and service accounts are skipped by the listener.
- **Scale:** replay needs no full scan on the Conversa side, so it does not depend on an `updated_since` filter.
- **Tests:** a replayed `user.created` and `user.updated` reach the handler, and duplicate replays are idempotent. The existing handler tests already cover the upsert and skip rules.

## Out of Scope (this change)

- Backfill and periodic reconcile. Planned for a later phase, by event replay (see Phase 2). No Identies list endpoint is needed.
- Offboarding (`user.offboarding_scheduled`). Needs its payload verified first.
- Syncing agents and service accounts. Chat is for humans; this is open until decided (open question 1).
- Any change to the context pack contract, merge logic, or fetcher.
- Changing the Telegram link flow's user-facing behaviour.
- A `updated_at` ordering column (see Event handling).

## Open Questions

1. **Agents and service accounts:** should they get context? The default is no. Confirm before implementation.
2. **Event replay for backfill:** can Identies republish `user.created` and `user.updated` for existing humans, and on which subject? The worker's consumer uses `DeliverPolicy.LAST`, so replayed history needs a separate consumer or a live replay subject. Decide with the Identies owners before the phase 2 work starts. Conversa does not need a list endpoint.
3. **Event prefix: resolved.** Production publishes `com.identies.*` (confirmed by the Conversa team). The prefix is now the setting `IDENTIES_EVENT_PREFIX`, defaulting to `com.identies`. The NATS subscription and every event name are derived from it (`app/core/identies_events.py`).
4. **Chat-assistant users and `user.created`: answered.** Any authenticated request to Identies onboards the user (`identies/app/middleware/authentication_middleware.py` calls `UserHandler.resolve_user`), and that publishes `user.created`. A user who signs in through Auth0 and calls the Conversa API directly is onboarded by Conversa's SDK middleware, which calls Identies' `/userinfo` with the same token. That call runs Identies' onboarding first, so Identies creates the user and publishes the event. Conversa then creates its local row. Both writes are upserts, so either order is safe. The event and the first chat can each queue an initial sync, which is harmless because sync is idempotent.
5. **Offboarding payload:** confirm `user.offboarding_scheduled` carries the user id and what the sync should do on it.
6. **Reconcile frequency:** is hourly right? It trades Identies load against how long a missed event stays missed.

## Further Notes

- Findings from this work, recorded so they are not rediscovered:
  - `DetachedInstanceError` in `sync_context_all_due_task`: the managed session commits and expires rows on exit. Read ids inside the session (fixed in #143).
  - The `fastapi` pin must be a valid Poetry constraint. `=v0.159.1` broke the Docker build on Poetry 2.1.2 (fixed in #144).
  - Beat runs in the infra compose file (`conversa-beat`), not from this repo. Do not add a Beat entry point here.
  - The release verifier needs a successful `Python checks` run on the release commit. Run it only after the post-merge CI finishes.
- Open items from this work: phase 2 replay design (open question 2), offboarding payload (open question 5), agents and service accounts (open question 1), reconcile frequency (open question 6, now replaced by event resend).
- Identies publishes these events on a best-effort basis, with no outbox. Event-driven registration alone is not enough, which is why reconciliation is a required later phase.
- Prerequisite that is now done: the due-pairs query no longer caps users or sources. Production has about 20 users today, so the old cap was a latent bug, not an active outage. It would have silently skipped users beyond 1000 (or sources beyond 200), so it is fixed before this listener adds more users.
