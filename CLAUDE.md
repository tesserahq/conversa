# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Conversa

Conversa is a conversational interface gateway for the Tessera platform. It acts as a channel adapter and orchestration layer — users interact via messaging platforms (Telegram first, then WhatsApp, web chat, voice, etc.) and Conversa delegates all reasoning and data access to Tessera via APIs and MCP. It owns no business data and implements no domain logic.

## Commands

```bash
# Install dependencies
poetry install

# Run dev server (hot reload, port 8000)
poetry run dev

# Run all tests
poetry run pytest tests/

# Run a single test file
poetry run pytest tests/app/repositories/test_user_repository.py -v

# Run a single test function
poetry run pytest tests/app/repositories/test_user_repository.py::test_function_name -v

# Lint (syntax errors and undefined names only)
poetry run ruff check --select=E9,F63,F7,F82

# Lint (all issues, non-blocking)
poetry run ruff check --exit-zero

# Check formatting
black . tests/ --check --verbose

# Auto-format
black . tests/

# Run Celery worker
poetry run worker

# Run NATS worker
poetry run nats_worker

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Architecture

### Layer Overview

```
Channel Plugins (channels/plugins/)
    ↓
FastAPI Gateway (routers/, core/)    ← sessions, auth, message routing, LLM orchestration
    ↓
Repositories + Models               ← SQLAlchemy + PostgreSQL
    ↓
External: Tessera SDK, MCP servers, Redis, NATS
```

### Key Directories

- **`app/routers/`** — API endpoints: sessions, context sources, credentials, system prompts, MCP servers
- **`app/channels/`** — Multi-channel plugin architecture. `base.py` defines the abstract plugin contract; `plugins/telegram/` is the only current implementation. New channels implement `base.py`.
- **`app/core/`** — Stateful logic: `routing.py` (message routing), `linker.py` (onboarding), `registry.py` (channel plugin registry), `credentials.py` (Fernet encryption)
- **`app/repositories/`** — Repository pattern over SQLAlchemy models; all DB access goes through here
- **`app/mcp/`** — MCP integration: catalog discovery, client factory, tool execution
- **`app/tasks/`** — Celery tasks: context sync (periodic), NATS event processing
- **`app/infra/`** — Celery app config, logging, telemetry

### Chat Message Flow

1. Channel webhook hits `/sessions/{session_id}/messages`
2. Router normalizes message into `Envelope`
3. Session context + user profile loaded from DB
4. Context snapshot fetched (merged from registered context sources)
5. LLM called (pydantic-ai) with context + available MCP tools
6. Response routed back through channel plugin
7. Message persisted; events published to NATS (if enabled)

### Context Snapshot Flow

Context sources are external pull endpoints (Prometheus-style). A Celery Beat task runs every ~10 min, fetches all registered sources, merges them into a `context_snapshot` record. At chat time, Conversa reads the single latest snapshot — no fan-out at inference time.

### Important Patterns

- **Soft deletes**: `SoftDeleteMixin` auto-filters `deleted_at IS NOT NULL` records — don't forget this when writing raw queries
- **Async-first**: `asyncpg` driver, async SQLAlchemy 2.0, async Celery tasks throughout
- **Auth**: `AuthenticationMiddleware` + `UserOnboardingMiddleware` from Tessera SDK; set `DISABLE_AUTH=true` to bypass in dev
- **Credential encryption**: Fernet symmetric encryption; key from `CREDENTIAL_MASTER_KEY` env var
- **Test DB**: Tests auto-select a separate DB URL when `ENV=test`; fixtures in `tests/fixtures/` and `tests/conftest.py` patch Tessera SDK auth

## CI

GitHub Actions runs on push/PR to `main`:
1. Spins up PostgreSQL 18 + Redis 8
2. `ruff` lint + `black` format check
3. `pytest` full suite

Docker image built and pushed to Docker Hub on successful main builds.
