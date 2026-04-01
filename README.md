<p align="center">
  <img width="90px" src="assets/logo.png">
  
  <h1 align="center">Conversa</h1>
  
  <p align="center">
    The conversational interface service for the Tessera platform
  </p>
</p>

## Why "Convesa"?

**Conversa** is the conversational interface service for the Tessera platform.

It acts as a channel adapter and orchestration layer that enables users to interact with Tessera resources through conversational platforms (Telegram initially, later WhatsApp, web chat, voice, etc.), while keeping Tessera API- and MCP-centric.

Conversa does not own business data and does not implement domain logic.
All reasoning and data access are delegated to Tessera via APIs and MCP.

## Channels

### Slack

Slack uses Socket Mode (WebSocket-based), so no public webhook URL is required.

#### 1. Create a Slack App

Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app **From scratch**.

#### 2. Generate the App-Level Token (`SLACK_APP_TOKEN`)

Under **Settings → Basic Information → App-Level Tokens**, click **Generate Token and Scopes**:

| Scope | Purpose |
|---|---|
| `connections:write` | Required for Socket Mode (WebSocket connection) |

This produces the `xapp-...` token — set it as `SLACK_APP_TOKEN`.

#### 3. Add Bot Token Scopes

Under **OAuth & Permissions → Scopes → Bot Token Scopes**, add:

| Scope | Purpose |
|---|---|
| `chat:write` | Send messages |
| `im:history` | Read DM message history |
| `im:read` | Read DM metadata |

#### 4. Enable Socket Mode

Under **Settings → Socket Mode**, toggle **Enable Socket Mode** on.

#### 5. Subscribe to Bot Events

Under **Event Subscriptions → Subscribe to bot events**, add:

- `message.im` — receive direct messages sent to the bot

#### 6. Enable OAuth & Install

Under **Settings → Manage Distribution**, enable public distribution if needed. Then install the app to a workspace via the `/oauth/slack/install` endpoint — this performs the OAuth flow and stores the per-workspace `xoxb-...` bot token automatically.

#### Environment Variables

```env
SLACK_ENABLED=true
SLACK_APP_TOKEN=xapp-...        # From step 2
SLACK_CLIENT_ID=...             # From Basic Information → App Credentials
SLACK_CLIENT_SECRET=...         # From Basic Information → App Credentials
SLACK_SIGNING_SECRET=...        # From Basic Information → App Credentials
SLACK_OAUTH_SUCCESS_URL=...     # Redirect URL after successful workspace installation
```