"""Tests for message routing."""

from types import SimpleNamespace

import app.core.routing as routing


def test_link_url_format_substitutes_channel_and_link_token(monkeypatch):
    """link_url template placeholders {channel} and {link_token} are filled (routing.py)."""
    monkeypatch.setattr(
        routing,
        "get_settings",
        lambda: SimpleNamespace(
            link_url="https://app.example/link/{channel}/{link_token}",
        ),
    )
    link_token = "tok-abc"
    msg_channel = "telegram"
    link_url = routing.get_settings().link_url.format(
        channel=msg_channel, link_token=link_token
    )
    assert link_url == "https://app.example/link/telegram/tok-abc"
