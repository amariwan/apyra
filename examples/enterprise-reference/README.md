# Apyra Enterprise Reference

Compact reference application demonstrating Apyra composition across packages:
PostgreSQL/SQLite persistence, transactional outbox, Redis Streams pub/sub,
idempotent consumption, workflow execution, JWT authentication/authorization,
OpenTelemetry, and structured logging.

## Run

```bash
uv run --project examples/enterprise-reference uvicorn main:app \
  --app-dir examples/enterprise-reference --host 127.0.0.1 --port 5000 --reload
```

## Configuration

Environment variables:

- `DATABASE_URL` — async SQLAlchemy URL (default `sqlite+aiosqlite:///./reference.db`).
  Use `postgresql+asyncpg://user:pass@host:5432/db` for PostgreSQL.
- `DB_BACKEND`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` — alternative Postgres config.
- `REDIS_URL` — Redis URL (default `redis://localhost:6379/0`).
- `APYRA_REFERENCE_JWT_SECRET` — HS256 signing key (dev default provided; set in production).
- `LOG_LEVEL`, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`.

## Test

```bash
uv run --project examples/enterprise-reference pytest
```

With real services:

```bash
DATABASE_URL='postgresql+asyncpg://itsaplan:itsaplan@localhost:5432/apyra_test' \
REDIS_URL='redis://localhost:6379/0' \
uv run --project examples/enterprise-reference pytest
```

## Endpoints

- `GET /api/health`
- `POST /api/auth/token?customer_id=...` — issue access token
- `POST /api/orders?customer_id=...` — create order (requires `orders:write`)
- `GET /api/orders/{id}` — get order (requires `orders:read`)
- `POST /api/orders/{id}/process` — run workflow (requires `orders:write`)
- `POST /api/publish-pending` — publish outbox to Redis Streams
- `POST /api/consume` — consume pending stream messages

## Migrations

Schema is created on startup via `Base.metadata.create_all`. For production,
use the `apyra-db[migrations]` extra (Alembic) to manage schema versions.
