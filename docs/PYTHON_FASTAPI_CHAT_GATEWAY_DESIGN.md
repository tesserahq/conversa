# Python/FastAPI Multi-Channel Chat Gateway Design

## Summary
Build a FastAPI-based gateway that connects to multiple chat providers via plugins. Each plugin encapsulates transport (webhook/socket/polling/CLI), normalization, and outbound delivery. The gateway owns routing, session state, access policy, and interaction with the LLM runtime.

## Goals
- Connect to WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, Microsoft Teams, WebChat.
- Support webhooks, sockets/gateways, long polling, and CLI bridges.
- Provide a uniform inbound/outbound envelope.
- Deterministic routing: replies go back to the same channel + chat + thread.
- Per-channel policies: linking, allowlist, open, disabled.

## Non-goals
- Full UI product; WebChat is a minimal WebSocket interface.
- Automated provisioning of provider credentials.

## Architecture
```
+-------------------+      +------------------+      +--------------------+
|  Channel Plugins  | <--> |  Gateway Core    | <--> |  LLM Runtime/Worker |
| (Discord/Slack/…) |      |  (FastAPI)       |      | (separate service)  |
+-------------------+      +------------------+      +--------------------+
          |                          |
          |                          v
          |                   +--------------+
          |                   | Session/State|
          |                   | Store        |
          |                   +--------------+
          |
          v
  External Provider APIs
```

## Module Layout
```
app/
  core/
    config.py
    runtime.py
    registry.py
    routing.py
    session_store.py
    auth.py
    logs.py
  channels/
    base.py
    dock.py
    envelope.py
    policies.py
    registry.py
    plugins/
      whatsapp/
      telegram/
      slack/
      discord/
      googlechat/
      signal/
      imessage/
      msteams/
      webchat/
  gateway/
    api.py
    ws.py
    webhooks.py
  workers/
    llm.py
    queue.py
  tests/
```

## Core Concepts

### Uniform Message Envelope
```python
class InboundMessage(BaseModel):
    channel: str
    account_id: str | None
    sender_id: str
    chat_id: str
    thread_id: str | None
    message_id: str
    text: str | None
    media: list[Media] = []
    timestamp: datetime
    raw: dict

class OutboundMessage(BaseModel):
    channel: str
    account_id: str | None
    chat_id: str
    thread_id: str | None
    text: str | None
    media: list[Media] = []
    reply_to: str | None
```

### Plugin Contract
```python
class ChannelPlugin(Protocol):
    id: str
    meta: ChannelMeta
    capabilities: ChannelCapabilities

    def configure(self, cfg: AppConfig) -> None: ...
    def start(self, runtime: Runtime) -> None: ...
    def stop(self) -> None: ...

    def inbound(self, event: InboundEvent) -> None: ...
    def outbound(self, msg: OutboundMessage) -> SendResult: ...

    def actions(self) -> ChannelActions | None: ...
    def linking(self) -> linkingAdapter | None: ...
    def status(self) -> ChannelStatusAdapter | None: ...
```

### Plugin Registration
```python
registry.register_channel(plugin)
registry.register_http_handler(path, handler)
registry.register_ws_handler(path, handler)
```

## Channel Transport Modes
- WhatsApp: WhatsApp Web socket (Baileys-like). No webhook.
- Telegram: Bot API. Long polling default, webhook optional.
- Slack: Socket Mode (websocket) default; HTTP Events API optional.
- Discord: Gateway websocket.
- Google Chat: HTTP webhook only.
- Signal: `signal-cli` JSON-RPC + SSE daemon.
- iMessage: legacy `imsg` JSON-RPC over stdio; BlueBubbles is webhook + REST.
- Microsoft Teams: Bot Framework webhook endpoint.
- WebChat: Gateway WebSocket.

## Access Policy & linking
- `linking`: unknown senders must be approved; generate short code. Use the Tessera SDK, create_link_token from the Identies client. 

linking flow:
1. Unknown sender arrives.
2. Generate code;
3. Send code to the user so the account can be linked.

## Session Model
- Session key: `agent:<id>:<channel>:<chat_id>`
- Store in DB with recent messages and routing metadata.

## How Plugins Interact With the LLM

### Flow Overview
1. **Inbound event** arrives (webhook/socket/polling).
2. Plugin **normalizes** provider payload to `InboundMessage`.
3. Gateway **applies policy** (linking).
4. Gateway **builds LLM request**:
   - session history
   - system prompt
   - channel metadata (channel id, sender id, chat id, thread id)
   - any tool schema for allowed actions
5. LLM produces a response:
   - plain text reply
   - optional tool calls (actions like send, react, edit, fetch context)
6. Gateway **routes response** to same channel:
   - converts to `OutboundMessage`
   - calls plugin `outbound(...)`

### LLM Interaction Contract
- **Plugins do not call the LLM directly.** They only emit normalized events and send outbound payloads.
- The **gateway core** is the only component that interacts with the LLM runtime.
- Plugins can expose **capabilities** that influence LLM behavior:
  - supported media types
  - max text length
  - reply threading support
  - reactions/polls

### Optional Tooling and Actions
- Plugins may register **message actions** (react, edit, delete, typing).
- The gateway includes these in LLM tool schema for channels where:
  - the action is supported
  - policy allows usage

### Safety Boundaries
- All LLM output is **post-processed** by the gateway before sending:
  - enforce max length
  - strip unsupported markdown/formatting
  - validate attachment size/type
  - reject disallowed actions

## FastAPI Integration
- `/health`
- `/channels/status`

Webhook endpoints:
- `/webhooks/telegram`
- `/webhooks/slack`
- `/webhooks/googlechat`
- `/webhooks/api/messages` (Teams)

WebSocket:
- `/ws/webchat`

## Observability
- Structured logs per channel and account.
- Metrics: inbound/outbound counts, webhook latency, socket reconnects.
- Health probes per channel.

## Implementation Order
1. Core registry + envelope + session store.
2. Telegram plugin (polling + optional webhook). Use python-telegram-bot.
