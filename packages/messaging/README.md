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

Contracts: `MessageEnvelope`, `MessagePublisher`, `MessageConsumer`, `MessageHandler`, `DeliveryContext`, `RetryPolicy`, `DeadLetterPolicy`, `IdempotencyStore`, `AtomicIdempotencyStore`. Implementations: `ExponentialBackoff`, `RedisStreamsPublisher`, `RedisStreamsConsumer`, `InMemoryIdempotencyStore`, `RedisIdempotencyStore`, `PostgresIdempotencyStore`, `ClaimResult`, and `IdempotencyClaimLostError`.

## Delivery semantics

The Redis Streams consumer guarantees **at-least-once** delivery: messages are acknowledged only
after the handler returns, and abandoned pending messages are recovered and re-processed. With a
`RetryPolicy`, failed messages are retried with exponential backoff up to `max_attempts` and then
sent to a dead-letter stream. Distributed idempotency stores (`RedisIdempotencyStore`,
`PostgresIdempotencyStore`) provide atomic claim/complete semantics for duplicate suppression.
Completing a claim after its owner lease expires or another worker takes it over raises
`IdempotencyClaimLostError`; consumers leave the delivery unacknowledged so it can be reconciled.

## Error behavior

Publish/consume errors propagate; retry/dead-letter behavior follows configured policies.

## Integration

Combine with `apyra-db` (outbox) and `apyra-events`. Real infrastructure tests require PostgreSQL and Redis.

## Compatibility

- Python ≥ 3.12

## License

MIT
