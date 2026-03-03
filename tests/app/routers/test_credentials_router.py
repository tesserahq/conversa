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


def test_list_credential_types(client):
    """GET /credentials/types returns available credential types and their attributes."""
    r = client.get("/credentials/types")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    type_names = [t["type_name"] for t in data]
    assert CredentialType.BEARER_AUTH in type_names
    assert CredentialType.BASIC_AUTH in type_names
    assert CredentialType.API_KEY in type_names
    assert CredentialType.M2M_IDENTIES in type_names
    assert CredentialType.DELEGATED_IDENTIES_EXCHANGE in type_names
    for t in data:
        assert "type_name" in t
        assert "display_name" in t
        assert "fields" in t
        assert isinstance(t["fields"], list)
    bearer = next(t for t in data if t["type_name"] == CredentialType.BEARER_AUTH)
    assert len(bearer["fields"]) == 1
    assert bearer["fields"][0]["name"] == "token"
    assert bearer["fields"][0]["input_type"] == "password"
    assert bearer["fields"][0]["required"] is True


@pytest.mark.parametrize(
    ("credential_type", "fields"),
    [
        (CredentialType.BEARER_AUTH, {"token": "secret-123"}),
        (
            CredentialType.BASIC_AUTH,
            {"username": "test-user", "password": "secret-pass"},
        ),
        (
            CredentialType.API_KEY,
            {"header_name": "X-Test-Key", "api_key": "api-key-secret"},
        ),
        (CredentialType.M2M_IDENTIES, {}),
        (
            CredentialType.DELEGATED_IDENTIES_EXCHANGE,
            {"audience": "api://resource", "scopes": ["read", "write"]},
        ),
    ],
)
def test_create_credential(client, setup_user, credential_type, fields):
    """POST /credentials creates credentials for all supported types."""
    payload = {
        "name": f"new-{credential_type}-cred",
        "type": credential_type,
        "fields": fields,
    }
    r = client.post("/credentials", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == f"new-{credential_type}-cred"
    assert data["type"] == credential_type
    assert "id" in data
    assert "encrypted_data" not in data
    assert "fields" not in data
    for field_value in fields.values():
        assert str(field_value) not in str(data)


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
    """POST with invalid credential fields returns 422 with structured details."""
    payload = {
        "name": "bad",
        "type": CredentialType.BEARER_AUTH,
        "fields": {},  # missing token
    }
    r = client.post("/credentials", json=payload)
    assert r.status_code == 422
    data = r.json()
    assert data["message"] == "Invalid credential fields"
    assert len(data["details"]) == 1
    assert data["details"][0]["loc"] == ["token"]
