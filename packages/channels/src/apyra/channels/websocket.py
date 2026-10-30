"""Thin FastAPI WebSocket adapter over a channel layer."""

from __future__ import annotations

from fastapi import WebSocket

from apyra.channels.layer import ChannelLayer


class WebSocketChannel:
    def __init__(self, layer: ChannelLayer) -> None:
        self._layer = layer

    async def stream(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        subscription = await self._layer.subscribe(channel)
        try:
            async for message in subscription:
                await websocket.send_json(message)
        finally:
            await subscription.close()


__all__ = ["WebSocketChannel"]
