# apyra-messaging

Messaging contracts and reliability primitives for Apyra.

## Purpose

`apyra-messaging` provides message envelopes, publisher/consumer contracts, retry/backoff, dead-letter policy, idempotency store, Redis Streams publisher/consumer, and a transactional outbox (with DB extra).

## Installation

```bash
uv add apyra-messaging                      # contracts
uv add "apyra-messaging[outbox]"            # + DB-backed outbox
uv add "apyra-messaging[redis]"             # + Redis Streams
```

## Minimal usage

```python
from apyra.messaging import MessageEnvelope, ExponentialBackoff

envelope = MessageEnvelope(payload={"hello": "world"})
```

## Optional dependencies

- `outbox`: `apyra-db`, `sqlalchemy>=2.0.0`
- `redis`: `redis>=5.0.0`

## Configuration

Outbox uses `apyra-db` session management. Redis backend accepts explicit connection parameters.

## Public API

Contracts: `MessageEnvelope`, `MessagePublisher`, `MessageConsumer`, `MessageHandler`, `DeliveryContext`, `RetryPolicy`, `DeadLetterPolicy`, `IdempotencyStore`. Implementations: `InMemoryIdempotencyStore`, `ExponentialBackoff`, `RedisStreamsPublisher`, `RedisStreamsConsumer`.

## Error behavior

Publish/consume errors propagate; retry/dead-letter behavior follows configured policies.

## Integration

Combine with `apyra-db` (outbox) and `apyra-events`. Real infrastructure tests require PostgreSQL and Redis.

## Compatibility

- Python ≥ 3.12

## License

MIT
