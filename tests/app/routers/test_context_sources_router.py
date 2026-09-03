"""Tests for context sources router."""

from uuid import uuid4

import pytest


def test_list_context_sources(client, setup_context_source):
    """GET /context-sources returns list of context sources."""
    r = client.get("/context-sources")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    items = data["items"]
    assert len(items) >= 1
    ids = [s["id"] for s in items]
    assert str(setup_context_source.id) in ids


def test_create_context_source(client, setup_credential):
    """POST /context-sources creates a context source."""
    payload = {
        "source_id": "linden-api",
        "display_name": "Linden API",
        "base_url": "https://api.linden.example.com",
        "credential_id": str(setup_credential.id),
        "capabilities": {"supports_etag": True, "supports_since_cursor": True},
        "poll_interval_seconds": 1800,
        "enabled": True,
    }
    r = client.post("/context-sources", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["source_id"] == "linden-api"
    assert data["display_name"] == "Linden API"
    assert data["credential_id"] == str(setup_credential.id)


def test_create_context_source_duplicate_source_id(client, setup_context_source):
    """POST with duplicate source_id raises error (500)."""
    payload = {
        "source_id": setup_context_source.source_id,
        "display_name": "Other",
        "base_url": "https://other.example.com",
    }
    r = client.post("/context-sources", json=payload)
    assert r.status_code == 422


def test_get_context_source_by_id(client, setup_context_source):
    """GET /context-sources/{id} returns a context source."""
    r = client.get(f"/context-sources/{setup_context_source.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == str(setup_context_source.id)
    assert data["source_id"] == setup_context_source.source_id


def test_get_context_source_not_found(client):
    """GET /context-sources/{id} returns 404 for unknown id."""
    r = client.get(f"/context-sources/{uuid4()}")
    assert r.status_code == 404


def test_update_context_source(client, setup_context_source):
    """PATCH /context-sources/{id} updates a context source."""
    payload = {"display_name": "Updated Name", "poll_interval_seconds": 7200}
    r = client.patch(f"/context-sources/{setup_context_source.id}", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Updated Name"
    assert data["poll_interval_seconds"] == 7200


def test_delete_context_source(client, setup_context_source):
    """DELETE /context-sources/{id} soft deletes a context source."""
    r = client.delete(f"/context-sources/{setup_context_source.id}")
    assert r.status_code == 204
    r2 = client.get(f"/context-sources/{setup_context_source.id}")
    assert r2.status_code == 404


def test_create_context_source_invalid_source_id(client):
    """POST with invalid source_id returns 422 (validation error)."""
    payload = {
        "source_id": "invalid_id!",  # invalid chars
        "display_name": "Test",
        "base_url": "https://example.com",
    }
    r = client.post("/context-sources", json=payload)
    assert r.status_code == 422


def test_create_context_source_invalid_base_url(client):
    """POST with invalid base_url returns 422."""
    payload = {
        "source_id": "test-source",
        "display_name": "Test",
        "base_url": "not-a-valid-url",
    }
    r = client.post("/context-sources", json=payload)
    assert r.status_code == 422


def test_list_sync_state_returns_states_for_source(
    client, setup_context_source_state, setup_user
):
    """GET /context-sources/{id}/sync-state returns states for the source."""
    r = client.get(
        f"/context-sources/{setup_context_source_state.source_id}/sync-state"
    )
    assert r.status_code == 200
    data = r.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["user_id"] == str(setup_user.id)
    assert items[0]["user_email"] == setup_user.email


def test_list_sync_state_filters_by_search(
    client, setup_context_source_state, setup_user
):
    """GET /context-sources/{id}/sync-state?search= filters by user email."""
    r = client.get(
        f"/context-sources/{setup_context_source_state.source_id}/sync-state",
        params={"search": "no-such-user-xyz"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_sync_state_not_found_for_unknown_source(client):
    """GET /context-sources/{id}/sync-state returns 404 for unknown source id."""
    r = client.get(f"/context-sources/{uuid4()}/sync-state")
    assert r.status_code == 404
