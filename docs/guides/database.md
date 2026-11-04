# Database

`apyra-db` provides async SQLAlchemy infrastructure, typed settings, session management, repository
helpers, pagination, and optional Alembic support.

## Install an adapter

```bash
uv add 'apyra-db[postgres]'
# Other supported extras: sqlite, mysql, migrations
```

## Create a session manager

```python
from apyra.db import DatabaseSessionManager, DbSettings, build_async_database_url

settings = DbSettings(
    db_enabled=True,
    db_backend="postgres",
    db_host="postgres",
    db_database="app",
    db_username="app",
    db_password="change-me",
)
manager = DatabaseSessionManager(build_async_database_url(settings))
```

Create the manager in the application composition root and close it during shutdown. Do not create a
new engine per request.

## Schema lifecycle

`ensure_db_schema` and SQLAlchemy `create_all` are suitable for controlled tests and small examples.
Production schema evolution should use reviewed migrations. The `migrations` extra installs
Alembic, but Apyra does not yet ship an Alembic environment or migration runner; apply the
versioned scripts in `docs/migrations/` through your chosen migration system. The enterprise
reference application currently uses startup schema creation; that is an example constraint, not a
general production recommendation.

Integration behavior must be tested against the real selected database. SQLite success does not
verify PostgreSQL locks, concurrency, or transaction semantics.
