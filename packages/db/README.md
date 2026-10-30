# apyra-db

Async database infrastructure and repositories for Apyra (SQLAlchemy 2.x).

## Installation

```bash
uv add apyra-db
# plus your driver, e.g. asyncpg / aiosqlite
```

## Quick usage

```python
from apyra.db import Base, DatabaseSessionManager, Repository, build_async_database_url, DbSettings

settings = DbSettings(db_enabled=True, db_backend="sqlite", db_database=":memory:")
manager = DatabaseSessionManager(build_async_database_url(settings), engine_kwargs={"echo": False})
```

## Key exports

- `Base`, `TimestampMixin`, `UUIDPrimaryKeyMixin`
- `DatabaseSessionManager`, `DatabaseManager`, `get_db_session`
- `Repository`, `Page`, `CursorPage`
- `DbSettings`, `get_db_settings`
- `build_async_database_url`, `build_sync_database_url`
- `ensure_db_schema`

## Documentation

See [`examples/database-api`](https://github.com/amariwan/apyra/tree/main/examples/database-api).

## License

MIT