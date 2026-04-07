"""Tests for OAuth router."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from app.routers import oauth_router


def test_slack_install_returns_authorize_url_json(client, monkeypatch):
    """POST /oauth/slack/install returns Slack authorize URL payload."""
    monkeypatch.setattr(
        oauth_router,
        "get_settings",
        lambda: SimpleNamespace(slack_client_id="client-123"),
    )

    response = client.post("/oauth/slack/install")

    assert response.status_code == 200
    data = response.json()
    assert "authorize_url" in data

    parsed = urlparse(data["authorize_url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "slack.com"
    assert parsed.path == "/oauth/v2/authorize"

    query = parse_qs(parsed.query)
    assert query["client_id"] == ["client-123"]
    assert query["scope"] == [oauth_router._SLACK_BOT_SCOPES]
    assert query["state"]


def test_slack_install_get_method_not_allowed(client):
    """GET /oauth/slack/install is no longer allowed."""
    response = client.get("/oauth/slack/install")
    assert response.status_code == 405


def test_slack_install_returns_503_when_not_configured(client, monkeypatch):
    """POST /oauth/slack/install fails when Slack client id is missing."""
    monkeypatch.setattr(
        oauth_router,
        "get_settings",
        lambda: SimpleNamespace(slack_client_id=None),
    )

    response = client.post("/oauth/slack/install")

    assert response.status_code == 503
    assert response.json()["detail"] == "Slack integration not configured"
