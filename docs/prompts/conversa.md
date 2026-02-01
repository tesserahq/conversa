# Conversa — Service Specification

## Overview

**Conversa** is an external chat integration service.

It provides a unified, platform-agnostic way to connect conversational platforms (Telegram initially, later WhatsApp, web chat, voice, etc.) to internal systems through a clean, normalized interface.

Conversa is intentionally **domain-agnostic**. It does not contain business logic, data models, or product-specific knowledge. Its sole responsibility is to act as a reliable, secure bridge between external chat platforms and internal services.

Conversa also persists conversational events (inbound messages and outbound responses) for observability, auditing, and analysis of how users interact with external chat platforms.

---

## Responsibilities

Conversa is responsible for:

- Integrating with external chat platforms
- Managing platform-specific webhooks and APIs
- Receiving, normalizing, and routing inbound messages
- Sending outbound messages and replies
- Handling platform-specific user identifiers
- Enforcing channel-level security constraints
- Applying rate limiting and abuse protection
- Normalizing metadata (locale, platform, timestamps, etc.)
- Persisting inbound and outbound chat messages for analytics and operational visibility

Conversa is not responsible for:

- Business or domain logic
- Data storage or mutation
- Authorization or permission decisions
- Conversation reasoning or intent resolution
- Long-term conversation memory
- Knowledge retrieval or AI orchestration
- Interpreting, classifying, or semantically enriching stored conversations

---

## High-Level Architecture

```
[ Chat Platform ]
    (Telegram, WhatsApp, Web)
           ↓
        Conversa
           ↓
   Internal Consumers
 (APIs, Agents, MCPs)
```

Conversa acts strictly as an integration and transport layer.

---

## Supported Platforms

Initial:
- Telegram

Planned:
- WhatsApp (Meta / Twilio)
- Web chat
- Voice platforms

Each platform integration is implemented as an isolated adapter.

---

## Core Concepts

### Platform Adapters

A platform adapter encapsulates all platform-specific logic, including:

- Webhook registration and verification
- Message parsing and formatting
- Platform-specific user identifiers
- Delivery guarantees and retries
- Platform constraints (message length, formatting, attachments)

Adapters expose a normalized message format to the Conversa core.

---

### Normalized Message Format

All inbound messages are converted into a common structure:

```json
{
  "channel": "telegram",
  "external_user_id": "string",
  "message_id": "string",
  "text": "string",
  "attachments": [],
  "metadata": {
    "locale": "en",
    "timestamp": "iso8601"
  }
}
```

This format is stable and independent of downstream consumers.

---

## Conversation Storage

Conversa persists conversational events to support:

- Understanding how users request and phrase information
- Debugging platform integrations
- Auditing message delivery and responses
- Improving downstream systems (APIs, agents, MCPs)

Stored data includes:
- Inbound messages from external platforms
- Outbound responses sent by Conversa
- Platform, channel, and timestamp metadata

Conversa treats stored conversations as immutable events.
It does not interpret, label, or reason over stored messages.
Any analysis or enrichment is expected to be performed by downstream systems.

---

### Outbound Messages

Conversa accepts normalized outbound messages and delegates delivery to the appropriate platform adapter.

Example:

```json
{
  "channel": "telegram",
  "external_user_id": "string",
  "text": "Your message here"
}
```

---

## Security Considerations

- External chat platforms are treated as untrusted surfaces
- Webhooks are verified where supported
- Inbound payloads are validated and sanitized
- Rate limits are enforced per platform and user
- No sensitive data is persisted within Conversa
- Stored conversations may be subject to retention, redaction, or deletion policies depending on platform and regulatory requirements

---

## Extensibility

New chat platforms can be added by implementing a new adapter without changes to:

- Existing adapters
- Normalized message contracts
- Downstream consumers

Conversa is designed to remain a thin, stable integration layer as platforms and internal systems evolve.