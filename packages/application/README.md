# apyra-application

Application-layer conventions for Apyra: use cases and application services.

## Purpose

`apyra-application` defines the application layer boundary between domain logic and infrastructure. It provides use-case and application-service contracts and application-level error types.

## Installation

```bash
uv add apyra-application
# or: pip install apyra-application
```

## Minimal usage

```python
from apyra.application import UseCase, ApplicationError

class CreateOrder(UseCase):
    async def execute(self, ...) -> ...:
        ...
```

## Optional dependencies

None.

## Configuration

No runtime configuration.

## Public API

- `UseCase` — application use-case contract
- `ApplicationError` — application-layer error type

## Error behavior

Application failures raise `ApplicationError`. Wrap domain/infrastructure errors at this boundary as appropriate.

## Integration

Depends on `apyra-core` and `apyra-domain`. Used by `apyra-messaging` and `apyra-workflow`.

## Compatibility

- Python ≥ 3.12
- Depends on `apyra-core>=0.1.0,<0.2.0`, `apyra-domain>=0.1.0,<0.2.0`

## License

MIT
