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
    """POST /credentials creates credentials for all supported types; response includes redacted field keys."""
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
    # Response includes redacted field keys so client knows fields were saved
    assert "fields" in data
    if fields:
        for key in fields:
            assert key in data["fields"]
            assert data["fields"][key] == "[REDACTED]"
    else:
        assert data["fields"] == {}
    # No raw secret values in response
    for field_value in fields.values():
        if isinstance(field_value, list):
            for v in field_value:
                assert str(v) not in str(data)
        else:
            assert str(field_value) not in str(data)


def test_get_credential(client, setup_credential):
    """GET /credentials/{id} returns a credential with redacted field keys."""
    r = client.get(f"/credentials/{setup_credential.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == str(setup_credential.id)
    assert data["name"] == setup_credential.name
    # Stored fields are returned with values redacted
    assert "fields" in data
    assert data["fields"] == {"token": "[REDACTED]"}


def test_get_credential_not_found(client):
    """GET /credentials/{id} returns 404 for unknown id."""
    r = client.get(f"/credentials/{uuid4()}")
    assert r.status_code == 404


def test_reveal_credential_fields(client, setup_user):
    """POST /credentials/{id}/reveal-fields returns decrypted field values."""
    payload = {
        "name": "Reveal Test",
        "type": CredentialType.DELEGATED_IDENTIES_EXCHANGE,
        "fields": {"audience": "api://test", "scopes": ["read"]},
    }
    r = client.post("/credentials", json=payload)
    assert r.status_code == 201
    cred_id = r.json()["id"]
    r2 = client.post(f"/credentials/{cred_id}/reveal-fields")
    assert r2.status_code == 200
    data = r2.json()
    assert data["fields"] == {"audience": "api://test", "scopes": ["read"]}


def test_reveal_credential_fields_not_found(client):
    """POST /credentials/{id}/reveal-fields returns 404 for unknown id."""
    r = client.post(f"/credentials/{uuid4()}/reveal-fields")
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


def test_create_credential_then_get_returns_redacted_fields(client, setup_user):
    """POST with fields then GET returns same credential with field keys redacted (fields are persisted)."""
    payload = {
        "name": "MCP",
        "type": CredentialType.DELEGATED_IDENTIES_EXCHANGE,
        "fields": {"audience": "api://resource", "scopes": ["read", "write"]},
    }
    r = client.post("/credentials", json=payload)
    assert r.status_code == 201
    created = r.json()
    cred_id = created["id"]
    assert created["fields"] == {"audience": "[REDACTED]", "scopes": "[REDACTED]"}
    r2 = client.get(f"/credentials/{cred_id}")
    assert r2.status_code == 200
    gotten = r2.json()
    assert gotten["name"] == "MCP"
    assert gotten["fields"] == {"audience": "[REDACTED]", "scopes": "[REDACTED]"}


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
