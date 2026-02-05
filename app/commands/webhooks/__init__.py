"""Webhook command handlers."""

from app.commands.base_telegram import BaseTelegramCommand
from app.commands.webhooks.telegram_command import TelegramWebhookCommand

__all__ = ["BaseTelegramCommand", "TelegramWebhookCommand"]
