# Client Context (`client_context`)

## Summary

`client_context` is an optional, free-form object that callers of `POST /chat/completions` can send to tell the assistant about the UI state the user is currently in — for example the `account_id` or `todo_list_id` of the screen they have open. Conversa appends it to the **system prompt** it sends to Modela, so the model can use those values directly instead of asking the user for ids the frontend already knows.

It is **advisory only**: it is client-supplied data, not an authorization grant, and must never be used for access-control decisions.

## Request shape

```json
POST /chat/completions
{
  "messages": [{"role": "user", "content": "Add 'buy milk' to this list"}],
  "stream": true,
  "session_id": "3f1c…",
  "client_context": {
    "account_id": "acc_123",
    "todo_list_id": "list_456"
  }
}
```

- Type: `dict[str, Any] | None` (`app/schemas/chat.py`, `ChatCompletionCreate.client_context`).
- Keys and values are arbitrary; Conversa does not validate or interpret them.
- Omitted, `null` or `{}` → nothing is added to the prompt.

## How it reaches Modela

```
chat_router.create_chat_completion          app/routers/chat_router.py
  └─ Router.route_api_message / stream_api_message   app/core/routing.py
       └─ LLMRunner.run / stream                     app/workers/llm.py
            └─ _build_completion_messages
                 └─ _format_client_context_for_prompt
                      → appended to the system message
                         → ModelaClient.stream_complete(messages=…)
```

Modela has no dedicated field for it. Conversa folds it into the **system message** (the first `CompletionMessage`), after the stored system prompt and after the context-snapshot block:

```
<system prompt from SystemPromptRepository / DefaultSystemPrompt>

User context (use when relevant):
Facts: {...}
Recents: [...]
Pointers: [...]

Current app context (use these values directly instead of asking the user for them):
{"account_id": "acc_123", "todo_list_id": "list_456"}
```

On the Modela side, caller `system` messages are merged into the model config's own system prompt (config prompt first, then Conversa's). Modela versions before the `fix/honor-caller-system-messages` change silently dropped `system` messages, so none of this — including the stored system prompt and the context snapshot — reached the model.

The object is serialized with `json.dumps(client_context, default=str)`, so non-JSON values (UUIDs, datetimes) are stringified. The messages list sent to Modela is then: this system message, the persisted session history, and the current user turn.

## Lifecycle

- **Per request, not persisted.** It is not stored on the session or in message history. Callers must resend it on every request where it applies; if the user navigates to another screen, send the new values.
- **API channel only.** Only `/chat/completions` accepts it. Channel plugins (Telegram, Slack) call `Router.route_to_llm`, which does not pass one.
- **Not logged.** The Modela dispatch log line summarizes the context snapshot but not `client_context`.

## Client context vs. context snapshot

| | Context snapshot | Client context |
|---|---|---|
| Source | Registered context sources, synced by Celery (see [Context Sources Sync](context-sources-sync.md)) | The calling UI, per request |
| Content | Facts / recents / pointers about the user | Ambient UI state (current ids, screen) |
| Stored | Yes, `context_snapshot` table | No |
| Prompt block | `User context (use when relevant):` | `Current app context (...)` |

## Security notes

- **Not an authz grant.** The model may pass these ids to MCP tools, but the tools/Tessera services must still enforce that the user can access them. Never trust `client_context` for access control.
- **It lands in the system prompt.** Because the content is placed in the system message, a caller can influence model instructions through it. That is acceptable for first-party UIs that already hold the user's token (they can say anything in the user turn anyway), but keep it to small, structured values — ids and flags, not user-authored free text.
- **No size limit is enforced.** Large objects increase token cost on every request; keep payloads small.
