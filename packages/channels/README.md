# apyra-channels

Realtime channel primitives for Apyra.

## Purpose

`apyra-channels` provides channel layer contracts and backends (in-memory, Redis) plus an optional FastAPI WebSocket channel. Useful for pub/sub and realtime messaging.

## Installation

```bash
uv add apyra-channels                        # core
uv add "apyra-channels[websocket]"          # + FastAPI WebSocket
uv add "apyra-channels[redis]"              # + Redis backend
```

## Minimal usage

```python
from apyra.channels import get_channel_layer

layer = get_channel_layer()
```

## Optional dependencies

- `websocket`: `fastapi>=0.115.0`
- `redis`: `redis>=5.0.0`

## Configuration

`ChannelSettings` / `ChannelBackend` via Pydantic Settings (`apyra.channels.settings`).

## Public API

- `ChannelLayer`, `ChannelSubscription`
- `MemoryChannelLayer` (`InMemoryChannelLayer`), `RedisChannelLayer`, `RedisClient`
- `WebSocketChannel` (optional, requires extra)
- `get_channel_layer`, `close_channel_layer`
- `ChannelSettings`, `ChannelBackend`, `get_channel_settings`

## Error behavior

Backend errors propagate; configuration errors raise during factory resolution.

## Integration

Combine with `apyra-fastapi` (WebSocket extra) for HTTP/WebSocket endpoints and `apyra-redis`-free Redis backend.

## Compatibility

- Python ≥ 3.12
- WebSocket extra requires FastAPI ≥ 0.115

## License

MIT
