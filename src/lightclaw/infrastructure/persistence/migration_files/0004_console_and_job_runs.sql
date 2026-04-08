CREATE TABLE IF NOT EXISTS console_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_console_users_username ON console_users (username);
CREATE INDEX IF NOT EXISTS ix_console_users_created_at ON console_users (created_at);

CREATE TABLE IF NOT EXISTS console_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_console_sessions_session_token ON console_sessions (session_token);
CREATE INDEX IF NOT EXISTS ix_console_sessions_username ON console_sessions (username);
CREATE INDEX IF NOT EXISTS ix_console_sessions_expires_at ON console_sessions (expires_at);

CREATE TABLE IF NOT EXISTS console_ownership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_console_ownership_resource_type ON console_ownership (resource_type);
CREATE INDEX IF NOT EXISTS ix_console_ownership_resource_id ON console_ownership (resource_id);
CREATE INDEX IF NOT EXISTS ix_console_ownership_username ON console_ownership (username);
CREATE UNIQUE INDEX IF NOT EXISTS uq_console_ownership_resource ON console_ownership (resource_type, resource_id);

CREATE TABLE IF NOT EXISTS runtime_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(128) NOT NULL UNIQUE,
    config_value TEXT NOT NULL DEFAULT '',
    is_secret BOOLEAN DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_runtime_config_config_key ON runtime_config (config_key);
CREATE INDEX IF NOT EXISTS ix_runtime_config_updated_at ON runtime_config (updated_at);

CREATE TABLE IF NOT EXISTS runtime_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_key VARCHAR(128) NOT NULL UNIQUE,
    state_value TEXT NOT NULL DEFAULT '',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_runtime_state_state_key ON runtime_state (state_key);
CREATE INDEX IF NOT EXISTS ix_runtime_state_updated_at ON runtime_state (updated_at);

CREATE TABLE IF NOT EXISTS job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id VARCHAR(255) NOT NULL UNIQUE,
    job_id VARCHAR(255) NOT NULL,
    trigger VARCHAR(64) NOT NULL DEFAULT 'manual',
    status VARCHAR(64) NOT NULL,
    input_prompt TEXT NOT NULL,
    output_text TEXT,
    error_message TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS ix_job_runs_run_id ON job_runs (run_id);
CREATE INDEX IF NOT EXISTS ix_job_runs_job_id ON job_runs (job_id);
CREATE INDEX IF NOT EXISTS ix_job_runs_status ON job_runs (status);
CREATE INDEX IF NOT EXISTS ix_job_runs_started_at ON job_runs (started_at);
