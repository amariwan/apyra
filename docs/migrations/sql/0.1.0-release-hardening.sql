-- Apply once after stopping Apyra outbox and workflow workers.
ALTER TABLE apyra_outbox ADD COLUMN leased_by VARCHAR(255);
ALTER TABLE apyra_outbox ADD COLUMN fencing_token VARCHAR(64);
ALTER TABLE apyra_outbox ADD COLUMN version_id INTEGER NOT NULL DEFAULT 0;

ALTER TABLE apyra_workflows ADD COLUMN leased_by VARCHAR(255);
ALTER TABLE apyra_workflows ADD COLUMN fencing_token VARCHAR(64);
ALTER TABLE apyra_workflows ADD COLUMN version_id INTEGER NOT NULL DEFAULT 0;
