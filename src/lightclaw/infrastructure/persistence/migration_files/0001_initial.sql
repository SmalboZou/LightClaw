CREATE TABLE IF NOT EXISTS session_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    name VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_session_messages_session_id ON session_messages (session_id);
CREATE INDEX IF NOT EXISTS ix_session_messages_created_at ON session_messages (created_at);

CREATE TABLE IF NOT EXISTS memory_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_memory_records_user_id ON memory_records (user_id);
CREATE INDEX IF NOT EXISTS ix_memory_records_created_at ON memory_records (created_at);

CREATE TABLE IF NOT EXISTS execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(255),
    event_type VARCHAR(128) NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_execution_logs_session_id ON execution_logs (session_id);
CREATE INDEX IF NOT EXISTS ix_execution_logs_event_type ON execution_logs (event_type);
CREATE INDEX IF NOT EXISTS ix_execution_logs_created_at ON execution_logs (created_at);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    cron VARCHAR(128) NOT NULL,
    enabled BOOLEAN DEFAULT 1,
    input_prompt TEXT NOT NULL,
    target_channel VARCHAR(128) NOT NULL,
    policy_mode VARCHAR(64) DEFAULT 'workspace_write',
    last_status VARCHAR(64),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_jobs_job_id ON jobs (job_id);
CREATE INDEX IF NOT EXISTS ix_jobs_created_at ON jobs (created_at);
CREATE INDEX IF NOT EXISTS ix_jobs_updated_at ON jobs (updated_at);
