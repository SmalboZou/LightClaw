ALTER TABLE execution_logs ADD COLUMN run_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_execution_logs_run_id ON execution_logs (run_id);
