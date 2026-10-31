# apyra-channels

Realtime channel primitives and pub/sub for Apyra.

## Installation

```bash
uv add apyra-channels
uv add 'apyra-channels[websocket]' # FastAPI WebSocket adapter
uv add 'apyra-channels[redis]' # Redis pub/sub backend
```

Without the `websocket` extra, the core channel layer remains usable without
FastAPI; `WebSocketChannel` is unavailable until FastAPI is installed.

## License

MIT
