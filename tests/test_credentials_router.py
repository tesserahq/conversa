"""Tests for credentials router."""

from uuid import uuid4

import pytest

from app.constants.credentials import CredentialType


def test_list_credentials(client, setup_credential):
    """GET /credentials returns list of credentials."""
    r = client.get("/credentials")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    items = data["items"]
    assert len(items) >= 1
    ids = [c["id"] for c in items]
    assert str(setup_credential.id) in ids


def test_create_credential(client, setup_user):
    """POST /credentials creates a credential."""
    payload = {
        "name": "new-bearer-cred",
        "type": CredentialType.BEARER_AUTH,
        "fields": {"token": "secret-123"},
    }
    r = client.post("/credentials", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "new-bearer-cred"
    assert data["type"] == CredentialType.BEARER_AUTH
    assert "id" in data
    assert "encrypted_data" not in data
    assert "token" not in str(data)


def test_get_credential(client, setup_credential):
    """GET /credentials/{id} returns a credential."""
    r = client.get(f"/credentials/{setup_credential.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == str(setup_credential.id)
    assert data["name"] == setup_credential.name


def test_get_credential_not_found(client):
    """GET /credentials/{id} returns 404 for unknown id."""
    r = client.get(f"/credentials/{uuid4()}")
    assert r.status_code == 404


def test_update_credential(client, setup_credential):
    """PATCH /credentials/{id} updates a credential."""
    payload = {"name": "renamed-cred"}
    r = client.patch(f"/credentials/{setup_credential.id}", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "renamed-cred"


def test_delete_credential(client, setup_credential):
    """DELETE /credentials/{id} soft deletes a credential."""
    r = client.delete(f"/credentials/{setup_credential.id}")
    assert r.status_code == 204
    r2 = client.get(f"/credentials/{setup_credential.id}")
    assert r2.status_code == 404


def test_create_credential_invalid_fields(client):
    """POST with invalid credential fields raises error (500)."""
    payload = {
        "name": "bad",
        "type": CredentialType.BEARER_AUTH,
        "fields": {},  # missing token
    }
    r = client.post("/credentials", json=payload)
    assert r.status_code == 500
