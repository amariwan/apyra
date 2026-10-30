# apyra-fastapi

FastAPI application factory and HTTP adapters for Apyra.

## Installation

```bash
uv add apyra-fastapi
```

## Quick usage

```python
from fastapi import APIRouter

from apyra.core import Settings
from apyra.fastapi import create_app

router = APIRouter()


@router.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from Apyra"}


app = create_app(title="My API", routers=[router], settings=Settings(api_prefix="/api"))
```

## Key exports

- `create_app` — application factory with security headers, CORS, rate limiting, health check
- `get_current_token`, `get_current_user`, `require_roles`, `require_scopes`
- `cbv`, `get`, `post`, `put`, `patch`, `delete` — class-based views
- `TimingMiddleware`, `register_timing_middleware`
- `set_operation_ids`, `simplify_operation_ids`

## Documentation

See [`examples/minimal-api`](https://github.com/amariwan/apyra/tree/main/examples/minimal-api) and
[`examples/authenticated-api`](https://github.com/amariwan/apyra/tree/main/examples/authenticated-api).

## License

MIT