from __future__ import annotations

from typing import Dict

from app.channels.base import ChannelPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._channels: Dict[str, ChannelPlugin] = {}

    def register_channel(self, plugin: ChannelPlugin) -> None:
        if plugin.id in self._channels:
            raise ValueError(f"Channel plugin already registered: {plugin.id}")
        self._channels[plugin.id] = plugin

    def get_channel(self, channel_id: str) -> ChannelPlugin | None:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[ChannelPlugin]:
        return list(self._channels.values())
