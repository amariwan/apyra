-- Apply only when using PostgresIdempotencyStore.
CREATE TABLE apyra_idempotency (
    message_id UUID PRIMARY KEY,
    status VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
