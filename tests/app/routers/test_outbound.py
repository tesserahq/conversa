"""Tests for outbound API."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db import get_db


@pytest.fixture
def client_with_db(db):
    """Client with db override and testing mode (no auth)."""
    app = create_app(testing=True)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_outbound_channel_not_enabled(client_with_db: TestClient):
    resp = client_with_db.post(
        "/outbound",
        json={
            "channel": "telegram",
            "external_user_id": "123",
            "text": "hi",
        },
    )
    assert resp.status_code == 400
    assert (
        "not enabled" in resp.json().get("detail", "").lower()
        or "not supported" in resp.json().get("detail", "").lower()
    )
