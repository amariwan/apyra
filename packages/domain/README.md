# apyra-domain

Domain primitives for Apyra: entities, value objects, domain events, and repository contracts.

## Purpose

`apyra-domain` provides framework-independent building blocks for domain-driven design: entities, value objects, domain events, and repository/unit-of-work contracts. It depends only on `apyra-core`.

## Installation

```bash
uv add apyra-domain
# or: pip install apyra-domain
```

## Minimal usage

```python
from apyra.domain import Entity, ValueObject, DomainEvent


class OrderId(ValueObject):
    value: str


class Order(Entity):
    id: OrderId
```

## Optional dependencies

None.

## Configuration

No runtime configuration. Domain primitives are pure Python.

## Public API

- `Entity` — base entity with identity
- `ValueObject` — immutable value object base
- `DomainEvent` — domain event base
- `Repository` — repository contract
- `UnitOfWork` — unit-of-work contract

## Error behavior

Domain validation errors surface as standard Python/Pydantic validation errors. No framework-specific error types beyond `apyra.core`.

## Integration

Combine with `apyra-application` for use cases and `apyra-messaging`/`apyra-db` for persistence and event publishing.

## Compatibility

- Python ≥ 3.12
- Depends on `apyra-core>=0.1.0,<0.2.0`

## License

MIT
