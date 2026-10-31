# apyra-events

Typed event bus and Redis Streams support for Apyra.

## Installation

```bash
uv add apyra-events
uv add 'apyra-events[redis]'    # Redis Streams client
uv add 'apyra-events[rabbitmq]' # aio-pika client
```

The Redis Streams adapter accepts a client implementing its async stream protocol; the `redis`
extra provides the standard `redis` client. RabbitMQ support uses `aio-pika`.

Custom `EventBus` subclasses should implement both `publish()` and `subscribe()`. Incomplete
subclasses remain temporarily instantiable for compatibility, emit `DeprecationWarning` when
defined, and raise `NotImplementedError` if a missing method is called. Abstract enforcement will
begin no earlier than the next major `apyra-events` release.

Redis subscriptions start reading from the stream's current tail. A `publish()` on the same bus waits
until that initial cursor is established, so publishing immediately after `subscribe()` does not
skip the new event. Entries already in the stream before the reader starts are not replayed.

## License

MIT
