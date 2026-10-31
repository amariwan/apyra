"""Realtime channel primitives for Apyra."""

from __future__ import annotations

from typing import Any

from .factory import close_channel_layer, get_channel_layer
from .layer import ChannelLayer, ChannelSubscription
from .memory import MemoryChannelLayer

InMemoryChannelLayer = MemoryChannelLayer
from .redis import RedisChannelLayer, RedisClient
from .settings import ChannelBackend, ChannelSettings, get_channel_settings

WebSocketChannel: Any = None
try:
    from .websocket import WebSocketChannel as _WebSocketChannel

    WebSocketChannel = _WebSocketChannel
except ModuleNotFoundError as _error:  # pragma: no cover - optional FastAPI integration
    if _error.name != "fastapi":
        raise

__all__ = [
    "ChannelBackend",
    "ChannelLayer",
    "ChannelSettings",
    "ChannelSubscription",
    "InMemoryChannelLayer",
    "MemoryChannelLayer",
    "RedisChannelLayer",
    "RedisClient",
    "WebSocketChannel",
    "close_channel_layer",
    "get_channel_layer",
    "get_channel_settings",
]
