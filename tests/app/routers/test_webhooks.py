"""Tests for webhook routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db import get_db


@pytest.fixture
def client_no_auth(db):
    """Client with db override and no auth (for webhooks)."""
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


def minimal_telegram_update():
    return {
        "update_id": 123,
        "message": {
            "message_id": 456,
            "from": {
                "id": 789,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "language_code": "en",
            },
            "chat": {
                "id": 789,
                "type": "private",
                "first_name": "Test",
                "last_name": "User",
            },
            "date": 1609459200,
            "text": "hello",
        },
    }


@patch("app.commands.base_telegram.get_settings")
def test_telegram_webhook_disabled(mock_settings, client_no_auth: TestClient):
    mock_settings.return_value.telegram_enabled = False
    mock_settings.return_value.telegram_bot_token = None
    mock_settings.return_value.telegram_webhook_secret = None
    resp = client_no_auth.post("/webhooks/telegram", json=minimal_telegram_update())
    assert resp.status_code == 503


@patch("app.commands.webhooks.telegram_command.get_settings")
@patch("app.commands.base_telegram.get_settings")
def test_telegram_webhook_invalid_secret(
    mock_base_settings, mock_cmd_settings, client_no_auth: TestClient
):
    settings = MagicMock()
    settings.telegram_enabled = True
    settings.telegram_bot_token = "fake"
    settings.telegram_webhook_secret = "secret"
    mock_base_settings.return_value = settings
    mock_cmd_settings.return_value = settings
    resp = client_no_auth.post(
        "/webhooks/telegram",
        json=minimal_telegram_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 403


@patch("app.commands.webhooks.telegram_command.get_settings")
@patch("app.commands.base_telegram.get_settings")
def test_telegram_webhook_success(
    mock_base_settings, mock_cmd_settings, client_no_auth: TestClient
):
    settings = MagicMock()
    settings.telegram_enabled = True
    settings.telegram_bot_token = "fake"
    settings.telegram_webhook_secret = None
    mock_base_settings.return_value = settings
    mock_cmd_settings.return_value = settings
    resp = client_no_auth.post("/webhooks/telegram", json=minimal_telegram_update())
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
