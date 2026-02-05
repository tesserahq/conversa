"""
Base command for Telegram-related operations.

Provides a shared way to obtain a configured TelegramAdapter for use across
webhook and outbound Telegram commands.
"""

from __future__ import annotations

from app.adapters.telegram import TelegramAdapter
from app.config import get_settings


class BaseTelegramCommand:
    """
    Base for Telegram-related commands.
    Provides a shared way to obtain a configured TelegramAdapter.
    """

    @staticmethod
    def get_telegram_adapter() -> TelegramAdapter | None:
        """Return configured TelegramAdapter or None if Telegram is disabled."""
        settings = get_settings()
        if not settings.telegram_enabled or not settings.telegram_bot_token:
            return None
        return TelegramAdapter(
            bot_token=settings.telegram_bot_token,
            webhook_secret=settings.telegram_webhook_secret,
        )
