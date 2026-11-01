# Messaging

`apyra-messaging` contains transport-neutral envelopes, publisher/consumer contracts, Redis Streams
adapters, transactional outbox support, retry policy, and idempotency stores. `apyra-events` provides
a lighter typed event bus plus Redis Streams and RabbitMQ adapters.

```bash
uv add 'apyra-messaging[redis,outbox]'
uv add 'apyra-events[redis]'
```

## Reliability model

- A transactional outbox records application state and an outgoing message in one database
  transaction, then publishes asynchronously.
- Redis Streams consumer groups provide at-least-once delivery. Consumers must be idempotent.
- A successful publish acknowledgement does not prove that every consumer completed.
- Retries can produce duplicates; Apyra does not claim exactly-once delivery.
- Dead-letter and retry policies must match the application's recovery procedure.

Use a stable message ID, persist idempotency state at the same durability level as the side effect,
and propagate trace context without including confidential payloads. Validate failure and recovery
against real PostgreSQL and Redis services before release.
