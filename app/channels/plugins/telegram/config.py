from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TelegramConfig:
    bot_token: str
    mode: str = "polling"  # polling | webhook
    webhook_path: str = "/webhooks/telegram"
    account_id: str = "default"
