-- Run after the schema upgrade, outside any explicit transaction block.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_apyra_outbox_poll
    ON apyra_outbox (status, next_attempt_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_apyra_outbox_lease
    ON apyra_outbox (status, lease_expires_at);
