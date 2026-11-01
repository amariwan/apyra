# apyra-events

Typed event bus primitives for Apyra.

## Purpose

`apyra-events` provides an event base type, an in-memory event bus, and Redis Streams / RabbitMQ backends for publishing and consuming typed events.

## Installation

```bash
uv add apyra-events                  # in-memory
uv add "apyra-events[redis]"        # + Redis Streams
uv add "apyra-events[rabbitmq]"    # + RabbitMQ (aio-pika)
```

## Minimal usage

```python
from apyra.events import Event, InMemoryEventBus

bus = InMemoryEventBus()
await bus.publish(Event())
```

## Optional dependencies

- `redis`: `redis>=5.0.0`
- `rabbitmq`: `aio-pika>=9.0.0`

## Configuration

No central settings object; backends accept explicit connection parameters.

## Public API

- `Event`, `EventBus`, `InMemoryEventBus`
- `RedisStreamEventBus`
- `RabbitMQEventBus`

## Error behavior

Backend connection/publish errors propagate from the underlying client.

## Integration

Use with `apyra-messaging` for envelopes/retry/idempotency and `apyra-fastapi` for HTTP-triggered events.

## Compatibility

- Python ≥ 3.12

## License

MIT
