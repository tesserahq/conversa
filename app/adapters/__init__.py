"""Platform adapters for chat integrations."""

from app.adapters.base import BasePlatformAdapter
from app.adapters.telegram import TelegramAdapter

__all__ = ["BasePlatformAdapter", "TelegramAdapter"]
