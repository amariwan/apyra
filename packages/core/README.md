# apyra-core

Core contracts, settings, and framework primitives for Apyra. Has no FastAPI or
infrastructure dependencies.

## Installation

```bash
uv add apyra-core
# or: pip install apyra-core
```

## Quick usage

```python
from apyra.core import Settings

settings = Settings(app_name="My API", api_prefix="/api")
print(settings.normalized_api_prefix())  # /api
```

## Key exports

- `Settings` — pydantic-settings with `APYRA_` env prefix
- `AuthenticationError`, `AuthorizationError` (re-exported where relevant)

## Documentation

See the [repository README](https://github.com/amariwan/apyra) and
[`docs/architecture/overview.md`](https://github.com/amariwan/apyra/blob/main/docs/architecture/overview.md).

## License

MIT