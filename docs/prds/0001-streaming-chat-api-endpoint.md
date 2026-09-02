## Implementation Issues

Broken into tracer-bullet vertical slices, in dependency order:

1. [tessera-sdk-py#96 — Async streaming method on ModelaClient](https://github.com/tesserahq/tessera-sdk-py/issues/96)
2. [conversa#63 — LLMRunner streaming migration + drop settings.llm_model](https://github.com/tesserahq/conversa/issues/63) (blocked by #96)
3. [conversa#64 — New chat endpoint: non-streaming happy path](https://github.com/tesserahq/conversa/issues/64) (blocked by #63)
4. [conversa#65 — SSE streaming on the chat endpoint](https://github.com/tesserahq/conversa/issues/65) (blocked by #64)
5. [conversa#66 — Disconnect-safe persistence for streamed chat replies](https://github.com/tesserahq/conversa/issues/66) (blocked by #65)
6. [conversa#67 — CORS allowlist + per-user rate limiting for the chat endpoint](https://github.com/tesserahq/conversa/issues/67) (blocked by #64)

Modela itself requires no issues/changes — its default-config resolution and streaming `/chat/completions` already support everything this PRD needs (verified against `create_completion_command.py`).

## Problem Statement

Today, the only way to talk to the LLM through Conversa is by going through a channel plugin — Telegram or Slack — which requires an external account, the Identies account-linking flow, and a chat platform in the loop. There is no way for a web frontend (or any other first-party client) to have a streaming conversation with the assistant while still getting Conversa's actual value-adds: server-side session persistence, context-snapshot injection, and knowing who the user is without re-deriving that on every call.

Separately, Modela already exposes a working, streaming, OpenAI-shaped `/chat/completions` endpoint, and Conversa already calls it (non-streaming only) from its Telegram/Slack path. That plumbing — delegated per-user M2M auth to Modela, context snapshot loading, session history — exists, but it's locked behind the channel-webhook path and it doesn't stream.

As a product/frontend team building a web chat experience against the Tessera platform, we want to point a standard chat UI (e.g. Vercel AI SDK's `useChat`, or any other OpenAI-compatible chat client) directly at Conversa and get a real, low-latency, streaming conversation — with the user already correctly identified from their session, their conversation persisted, and Conversa's context snapshot silently informing the assistant's answers.

## Solution

Add a new, browser-facing, streaming chat endpoint to Conversa that:

- Accepts an OpenAI-standard request body (`messages[]`, `stream`) so it's a drop-in target for standard OpenAI-compatible chat client libraries, while also accepting an optional `session_id` so repeat calls resume a real, persisted Conversa session instead of being purely stateless.
- Identifies the caller directly from their Tessera user JWT (via `tessera_sdk`'s existing `get_current_user`) — no Identies external-account-linking step, since the caller is already an authenticated platform user, not an anonymous external chat account.
- Streams the assistant's reply back as Server-Sent Events, in the same OpenAI `chat.completion.chunk` shape Modela's own endpoint already emits, via a new async streaming method added to `tessera-sdk-py`'s `ModelaClient` (which today only supports a blocking non-streaming call).
- Loads the same server-side session history and context snapshot that the Telegram/Slack path already uses, and persists the turn back to that session — including when the client disconnects before the stream finishes, so no generated content (and the cost incurred producing it) is silently lost.
- Leaves model selection entirely server-side: the caller never picks a model. Conversa stops sending an explicit model at all (retiring `settings.llm_model` as a concept, in both the new endpoint and the existing channel path) and relies on Modela resolving its own default chat `ModelConfig` (`is_default=True, config_type="chat"`), which Modela already supports today with zero changes needed on that side.
- Is gated by its own RBAC resource, independent of the existing `session` resource and of Modela's own `completion` resource.
- Ships with real CORS and per-user rate limiting, because this is the first Conversa endpoint designed to be called directly from a browser rather than server-to-server — today's `allow_origins=["*"]` and the unused `conversa_rate_limit_per_user_per_minute` setting are not adequate for that.

## User Stories

1. As a frontend developer, I want to point Vercel AI SDK's `useChat` (or any OpenAI-compatible chat client) at Conversa's new endpoint, so that I can build a chat UI without writing custom transport code.
2. As a frontend developer, I want the endpoint to accept the standard `{messages: [...], stream: true}` body shape, so that off-the-shelf OpenAI-compatible client libraries work without modification.
3. As a logged-in Tessera user, I want Conversa to know who I am from my existing session/JWT, so that I don't have to go through any account-linking flow to use the web chat.
4. As a logged-in Tessera user, I want my conversation history to persist across page reloads, so that I can continue a conversation later.
5. As a frontend developer, I want to pass a `session_id` on follow-up calls, so that Conversa uses its own persisted history and context snapshot instead of relying on me resending the entire conversation every time.
6. As a frontend developer, I want to omit `session_id` on the first call and receive one back, so that I can capture it for subsequent calls without a separate "create session" round trip.
7. As a user, I want to see the assistant's reply appear incrementally (token by token), so that the experience feels responsive rather than waiting for a full response.
8. As a user, I want the assistant's answers to reflect my current context (recent activity, facts, pointers Conversa already tracks), so that I don't have to re-explain things I've already told the platform elsewhere.
9. As a platform operator, I want the assistant's reply to be persisted to session history even if my browser tab closes mid-stream, so that the next message I send still has accurate context and Conversa isn't silently discarding content it already paid Modela to generate.
10. As a platform operator, I want the caller to never be able to choose an arbitrary Modela model/config, so that model selection, cost, and prompt configuration stay centrally controlled.
11. As a platform operator, I want this endpoint gated by its own RBAC permission, so that granting/revoking chat access doesn't also grant/revoke session-management or Modela-completion access.
12. As a platform operator, I want CORS restricted to known frontend origins, so that Conversa isn't an open proxy any browser page can call.
13. As a platform operator, I want per-user rate limiting on this endpoint, so that a single user (or a compromised token) can't run up unbounded LLM cost via a browser-facing endpoint.
14. As a platform operator, I want the existing Telegram/Slack path to keep working unchanged from the end user's perspective after this change, so that this feature doesn't regress the existing channel experience.
15. As a developer maintaining Conversa, I want a single code path in `LLMRunner` responsible for talking to Modela (streaming or not), so that Telegram/Slack and the new endpoint don't diverge into two different integrations with Modela over time.
16. As a developer maintaining `tessera-sdk-py`, I want a reusable async streaming method on `ModelaClient`, so that other SDK consumers besides Conversa can also consume Modela's streaming endpoint without reimplementing SSE parsing.
17. As a developer debugging a production issue, I want the new endpoint's request/response to carry identifying headers (session id, request id), consistent with the `X-Modela-Request-Id`/`X-Modela-Config-Slug` pattern Modela's own router already uses, so that I can correlate a browser request across Conversa and Modela logs.
18. As a QA engineer, I want a clear, testable answer for "what happens if the client disconnects mid-stream," so that this isn't a silent, unverified edge case in production.

## Implementation Decisions

**Request/response contract**
- New endpoint, new router (not added to `sessions_router.py`'s CRUD-style endpoints), exposing `POST /chat/completions`.
- Request body: OpenAI-standard shape — `messages: [{role, content}, ...]` plus `stream`. An optional `session_id` travels alongside it (extra body field), so standard OpenAI-compatible clients (which always resend full history) work unmodified, while Conversa still gets a real, continuable session.
- When `session_id` is present and resolves to an existing session: the resent `messages[]` history is ignored; only the newest (last) message's content is used as the new turn, combined with Conversa's own persisted session history (`SessionManager.get_history_for_llm`) and the user's latest context snapshot (`ContextSnapshotRepository.get_latest_snapshot`) — the same sources `Router.route_to_llm` already uses today.
- When `session_id` is absent (or doesn't resolve): Conversa creates a new session and returns its id to the client via a response header, following the existing `X-Modela-Request-Id` / `X-Modela-Config-Slug` header convention from Modela's `completion_router.py`. The response streams OpenAI-shaped `chat.completion.chunk` SSE events, matching what Modela's own `/chat/completions` already emits.
- `model` is never accepted from the caller for this endpoint (silently ignored, or rejected — implementer's call at build time) — model/config selection is entirely server-side via Modela's default `ModelConfig` resolution.

**Identity and session plumbing (reuse, not reinvent)**
- Caller identity comes directly from `tessera_sdk`'s `get_current_user` (same dependency Modela's own `completion_router.py` and Conversa's `sessions_router.py` already use) — no Identies `Linker` involvement for this endpoint.
- The new endpoint constructs a synthetic `InboundMessage` (`channel="api"`, `chat_id` = the session's existing chat_id when `session_id` is given, or a freshly generated id when starting a new session; `sender_id=str(user.id)`) and reuses `SessionManager.get_or_create_session` / `add_turn` / `get_history_for_llm` completely unmodified. This keeps session and message persistence identical in shape to the Telegram/Slack path — a session created via this endpoint is a normal `Session` row with `channel="api"`.
- When an explicit `session_id` is supplied, session lookup goes straight through `SessionRepository.get_session(session_id)` rather than key-based lookup, but still uses the same `SessionManager` for history/persistence.

**Streaming plumbing**
- `tessera-sdk-py`'s `ModelaClient` (`tessera_sdk/clients/modela/client.py`) is currently synchronous (`requests`-based `BaseClient`) and only exposes a blocking `complete()`. Add a new async method (e.g. `stream_complete()`) using an async HTTP client (httpx) that POSTs to Modela's `/chat/completions` with `stream=true`, parses the SSE `data: {...}` frames, and yields parsed delta chunks. This is additive — it does not change `complete()` or `BaseClient`.
- `LLMRunner` (`app/workers/llm.py`) becomes the single place in Conversa that talks to Modela. Its existing `run()` (which does `asyncio.to_thread(client.complete, ...)`) is replaced by a streaming method (e.g. `stream()`) that yields text deltas from `ModelaClient.stream_complete()`. Both call sites consume this same method:
  - The existing `Router.route_to_llm` (Telegram/Slack) awaits/joins all deltas into a single final string before building the `OutboundMessage`, since those channels don't support live-editing streaming.
  - The new endpoint forwards deltas live as SSE chunks to the browser.
- `LLMRunner` drops `model_name`/`settings.llm_model` — it stops passing an explicit `model` to Modela in all cases, relying on Modela's existing default-config resolution (`ModelConfigRepository.get_default()` via `CreateCompletionCommand._resolve_config(None)`), which requires no Modela-side changes.

**Disconnect-safe persistence**
- Streaming to Modela and persisting the resulting turn must not be tied to the lifetime of the browser's HTTP connection. The generation/accumulation/persistence work runs as a background `asyncio.Task`, decoupled from the `StreamingResponse` generator that feeds the client. The client-facing SSE generator reads chunks off that task's output (e.g. via a queue); if the client disconnects, the background task is unaffected and continues to completion, still calling `SessionManager.add_turn` with whatever was generated (full or partial).
- This is a new, narrowly-scoped piece of orchestration logic — it can live as a method on `Router` or as a small new service, whichever fits Conversa's existing module boundaries better at implementation time. It should not itself talk to Modela directly; it drives `LLMRunner.stream()`.

**Authorization**
- New RBAC resource (e.g. `"chat"`), built the same way as existing resources via `build_rbac_dependencies()` in `app/auth/rbac.py`, independent of the `"session"` resource (session read/write) and independent of Modela's own `"completion"` resource.

**CORS and rate limiting**
- Conversa's current CORS setup (`app/main.py`) is `allow_origins=["*"]` with a standing `# TODO: Restrict this` comment — acceptable for a server-to-server-only surface, not acceptable once a browser calls Conversa directly. This must become a real, env-driven origin allowlist as part of this work (at minimum scoped to the origins that will call the new endpoint; tightening it globally is preferable but is an operational decision, not a design one).
- Conversa already has an unused config field, `conversa_rate_limit_per_user_per_minute` (`app/config.py`), that nothing currently enforces. This work wires up actual per-authenticated-user rate limiting, at minimum on the new endpoint, using that existing setting.

**Headers**
- The response carries identifying headers following the existing convention (`X-Modela-Request-Id`, `X-Modela-Config-Slug` in `completion_router.py`): the new endpoint should similarly expose the session id (e.g. `X-Conversa-Session-Id`) so a client without a body-based mechanism for reading it can still capture it for the next call.

## Testing Decisions

Good tests here assert observable behavior (what gets sent to Modela, what gets persisted, what the HTTP client receives) rather than internal call sequencing. Given the scope, two pieces carry the real risk and get dedicated tests; the SDK boundary also gets a test since it's new, external-facing parsing logic.

- **`LLMRunner.stream()`**: mock `ModelaClient.stream_complete()` and assert (a) deltas are correctly accumulated/forwarded in order, (b) the outgoing request to Modela never includes a `model` field, (c) system prompt and context-snapshot formatting are injected the same way the current `_build_completion_messages` does today (existing behavior, must not regress). Prior art: none directly (today's `LLMRunner` isn't unit tested against a mocked client in isolation per the codebase layout seen), so this establishes the pattern others should follow for this module going forward.
- **Disconnect-safe persistence task**: simulate a client disconnecting mid-stream (cancel/close the consuming side early) and assert the session still ends up with the generated content persisted via `SessionManager.add_turn`, exactly once — no double-writes if both the foreground SSE generator and the background task somehow both attempt to persist.
- **`ModelaClient.stream_complete()` (tessera-sdk-py)**: test against a mocked SSE response (well-formed chunks, a malformed/truncated chunk, and a stream that ends without a `[DONE]` sentinel) and assert correct chunk parsing/yielding and a clear error/termination behavior on the bad-stream cases. Prior art: existing SDK tests in `tests/` for `ModelaClient.complete()` and other sync client methods, adapted for the async/streaming shape.

The new `chat_router` endpoint's request/response contract (session_id present vs. absent, RBAC denial, SSE chunk shape, response header) is lower priority for dedicated tests in this PRD's scope — it's largely a thin composition of the modules above — but should still get basic coverage consistent with how `sessions_router.py`'s endpoints are tested today, if time allows.

## Out of Scope

- Exposing model/`ModelConfig` selection to API callers.
- Streaming replies back through Telegram/Slack (live-editing outbound messages) — those channels continue to receive one final joined message.
- Any changes to Modela itself — its `/chat/completions` streaming endpoint and default-config resolution already support everything this PRD needs.
- Tool/MCP invocation from this new endpoint beyond whatever `LLMRunner`/Modela already do by default.
- A general-purpose API-key or service-to-service auth mode for this endpoint (only direct Tessera user JWTs are supported, per this PRD).
- Global CORS hardening beyond what's required to safely serve this endpoint (broader origin-allowlist cleanup across all of Conversa's other routes is a separate concern).
- Rate limiting for non-authenticated or non-user-scoped abuse patterns (e.g. IP-based limits, WAF-level protection) — only per-authenticated-user limiting is in scope here.

## Further Notes

- Confirmed during design: Modela's `CreateCompletionCommand._resolve_config(model_slug)` already falls back to `ModelConfigRepository.get_default()` when no `model` is supplied, so "stop sending a model" requires zero Modela-side changes — this was verified directly against `app/commands/completions/create_completion_command.py` in the modela repo, not assumed.
- The synthetic-`InboundMessage` approach for the new `channel="api"` sessions means no schema or model changes are needed to `Session`/`SessionMessage` — they already accept an arbitrary `channel` string and don't assume Telegram/Slack semantics beyond `chat_id`/`thread_id` being strings.
- `settings.llm_model` removal touches the existing Telegram/Slack path too (per an explicit decision made during design, to avoid two divergent model-selection mechanisms coexisting) — implementers should confirm no other code or documentation still references it before removing it.
