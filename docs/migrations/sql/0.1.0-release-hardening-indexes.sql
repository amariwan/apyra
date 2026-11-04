-- Apply after the schema upgrade. Use only when a short write-blocking index build is acceptable.
CREATE INDEX ix_apyra_outbox_poll ON apyra_outbox (status, next_attempt_at);
CREATE INDEX ix_apyra_outbox_lease ON apyra_outbox (status, lease_expires_at);
