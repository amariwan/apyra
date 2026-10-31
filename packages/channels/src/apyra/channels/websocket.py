"""Thin FastAPI WebSocket adapter over a channel layer."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from apyra.channels.layer import ChannelLayer


class WebSocketChannel:
    """Forward outbound channel messages to a FastAPI WebSocket connection."""

    def __init__(self, layer: ChannelLayer) -> None:
        self._layer = layer

    async def stream(self, websocket: WebSocket, channel: str) -> None:
        """Send channel messages until the client disconnects; inbound frames are ignored."""
        subscription = await self._layer.subscribe(channel)
        receiver: asyncio.Task[Any] | None = None
        message_reader: asyncio.Task[Any] | None = None
        sender: asyncio.Task[None] | None = None
        try:
            await websocket.accept()
            receiver = asyncio.create_task(websocket.receive())
            message_reader = asyncio.create_task(anext(subscription))
            while True:
                assert receiver is not None and message_reader is not None
                pending = [receiver, sender or message_reader]
                done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                if receiver in done:
                    received = receiver.result()
                    if received["type"] == "websocket.disconnect":
                        return
                    receiver = asyncio.create_task(websocket.receive())

                if sender is not None:
                    if sender in done:
                        sender.result()
                        sender = None
                        message_reader = asyncio.create_task(anext(subscription))
                elif message_reader in done:
                    try:
                        message = message_reader.result()
                    except StopAsyncIteration:
                        return
                    sender = asyncio.create_task(websocket.send_json(message))
        finally:
            tasks: list[asyncio.Task[Any]] = []
            if receiver is not None:
                tasks.append(receiver)
            if message_reader is not None:
                tasks.append(message_reader)
            if sender is not None:
                tasks.append(sender)
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await subscription.close()


__all__ = ["WebSocketChannel"]
