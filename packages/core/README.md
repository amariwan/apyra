# apyra-core

Core contracts, settings, and framework primitives for Apyra. Has no FastAPI or infrastructure dependencies.

## Purpose

`apyra-core` is the foundation of the Apyra framework. It provides shared settings, error types, and framework primitives used by every other `apyra.*` package. It intentionally depends only on Pydantic and Pydantic Settings so it can be used in any Python 3.12+ project without pulling in FastAPI or infrastructure.

## Installation

```bash
uv add apyra-core
# or: pip install apyra-core
```

## Minimal usage

```python
from apyra.core import Settings

settings = Settings(app_name="My API", api_prefix="/api")
print(settings.normalized_api_prefix())  # /api
```

## Optional dependencies

None. `apyra-core` ships no extras.

## Configuration

Settings use Pydantic Settings with the `APYRA_` environment prefix (for example `APYRA_APP_NAME`). See `apyra.core.Settings` for the full list of fields and defaults.

## Public API

- `Settings` — pydantic-settings base with `APYRA_` env prefix
- `ApyraError` — base framework exception
- `ConfigurationError` — raised for invalid configuration
- `__version__` — package version string

## Error behavior

Configuration problems raise `ConfigurationError` (a subclass of `ApyraError`). Unexpected framework failures raise `ApyraError`. No secrets or credentials are included in error messages.

## Integration

`apyra-core` is a dependency of every other `apyra.*` package. Install it directly only when you need settings and primitives without the rest of the framework.

## Compatibility

- Python ≥ 3.12
- Pydantic ≥ 2.8
- Pydantic Settings ≥ 2.4
- Semantic versioning; public API changes are documented in the changelog.

## License

MIT
