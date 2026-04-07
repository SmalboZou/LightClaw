import sqlite3
from pathlib import Path
import shutil
import uuid

from lightclaw.infrastructure.persistence.database import create_session_factory, get_migration_status


def test_migration_status_reports_latest_for_fresh_database() -> None:
    workspace = _make_test_workspace()
    database_url = f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}"
    try:
        create_session_factory(database_url)
        status = get_migration_status(database_url)

        assert status["current_version"] == status["latest_version"]
        assert status["pending_versions"] == []
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_migration_runner_upgrades_legacy_jobs_schema() -> None:
    workspace = _make_test_workspace()
    db_path = workspace / "legacy.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    try:
        _create_legacy_schema(db_path)

        create_session_factory(database_url)

        status = get_migration_status(database_url)
        assert status["current_version"] == status["latest_version"]

        with sqlite3.connect(db_path) as connection:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            assert "target_destination" in columns
            assert "last_run_at" in columns
            assert "last_output" in columns
            assert "skills" in columns
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _create_legacy_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_version VARCHAR(64) UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE jobs (
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

            INSERT INTO schema_metadata (schema_version) VALUES ('0001_initial');
            """
        )
        connection.commit()


def _make_test_workspace() -> Path:
    workspace = Path("tests/.tmp") / str(uuid.uuid4())
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()
