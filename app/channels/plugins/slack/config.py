from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SlackConfig:
    app_token: str  # xapp-... Socket Mode app-level token
    client_id: str
    client_secret: str
    signing_secret: str
    oauth_success_url: str = "/"
