# apyra-db

Async database infrastructure for Apyra.

## Purpose

`apyra-db` provides async SQLAlchemy-based database access: engine/session management, declarative base mixins, repository base, and pagination helpers. Supports PostgreSQL, MySQL, and SQLite via optional extras.

## Installation

```bash
uv add apyra-db                      # core (SQLAlchemy)
uv add "apyra-db[postgres]"          # + asyncpg/psycopg
uv add "apyra-db[mysql]"             # + asyncmy/pymysql
uv add "apyra-db[sqlite]"            # + aiosqlite
uv add "apyra-db[migrations]"        # + alembic
```

## Minimal usage

```python
from apyra.db import DatabaseSessionManager, get_db_session, Base

manager = DatabaseSessionManager(database_url="sqlite+aiosqlite:///./app.db")
```

## Optional dependencies

- `postgres`: `asyncpg`, `psycopg[binary]`
- `mysql`: `asyncmy`, `pymysql`
- `sqlite`: `aiosqlite`
- `migrations`: `alembic`

## Configuration

`DatabaseSettings` / `DbSettings` via Pydantic Settings. Environment prefix and fields are defined in `apyra.db.settings`.

## Public API

- `Base`, `TimestampMixin`, `UUIDPrimaryKeyMixin`
- `DatabaseManager`, `DatabaseSessionManager`, `get_db_session`, `get_sessionmanager`, `ensure_db_schema`
- `Repository`, `Page`, `CursorPage`
- `DatabaseSettings`, `DbSettings`, `get_db_settings`
- `build_async_database_url`, `build_sync_database_url`

## Error behavior

Database errors propagate as SQLAlchemy exceptions. Connection/configuration problems raise `ConfigurationError` where validated.

## Integration

Used by `apyra-messaging` (outbox) and `apyra-workflow`. Combine with `apyra-fastapi` for request-scoped sessions.

## Compatibility

- Python ≥ 3.12
- SQLAlchemy ≥ 2.0.30

## License

MIT
