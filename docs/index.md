# Conversa Documentation

Welcome to the Conversa documentation! Conversa is the **conversational interface gateway** for the Tessera platform, acting as a channel adapter and orchestration layer between messaging platforms and Tessera.

## What is Conversa?

Users interact via messaging platforms — Telegram first, then WhatsApp, web chat, voice, and others — and Conversa delegates all reasoning and data access to Tessera via APIs and MCP. Conversa owns no business data and implements no domain logic of its own.

**Conversa** reflects the service's purpose: it is the surface a user actually talks to, translating between chat platforms and the Tessera services that do the real work.

## Core Responsibilities

- Adapt inbound/outbound messages across channel plugins (Telegram, and future channels) into a single internal `Envelope` format
- Route messages to the LLM/orchestration layer and manage session state
- Keep a low-latency, chat-time-ready snapshot of user context pulled from registered context sources
- Handle credentials, MCP tool delegation, and onboarding/linking without embedding product-specific business logic

## Getting Started

- **[User Context Design](conversa-context.md)** — the Context Pack + Snapshot design: why Conversa needs a Source Registry, how it stays product-agnostic, and the phased rollout plan
- **[Context Sources Sync](context-sources-sync.md)** — how the sync worker actually pulls, merges, and stores context snapshots, and how chat requests read them
- **[Gateway Design](PYTHON_FASTAPI_CHAT_GATEWAY_DESIGN.md)** — overall FastAPI gateway architecture
- **[Telegram Workflow](telegram-request-workflow.md)** — how an inbound Telegram message is authenticated and routed
