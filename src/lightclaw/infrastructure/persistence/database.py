from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


@dataclass(frozen=True)
class MigrationFile:
    version: str
    filename: str


MIGRATIONS = [
    MigrationFile("0001_initial", "0001_initial.sql"),
    MigrationFile("0002_jobs_extended", "0002_jobs_extended.sql"),
    MigrationFile("0003_jobs_skills", "0003_jobs_skills.sql"),
    MigrationFile("0004_console_and_job_runs", "0004_console_and_job_runs.sql"),
    MigrationFile("0005_execution_logs_run_id", "0005_execution_logs_run_id.sql"),
]
LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version
SQLITE_BUSY_TIMEOUT_SECONDS = 5.0


def _prepare_sqlite_path(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    path_text = database_url.removeprefix("sqlite:///")
    db_path = Path(path_text)
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)


def create_session_factory(database_url: str) -> sessionmaker:
    _prepare_sqlite_path(database_url)
    engine = _create_database_engine(database_url)
    try:
        migrate_database(engine)
        return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    except Exception:
        engine.dispose()
        raise


def migrate_database(engine: Engine) -> None:
    _ensure_schema_metadata_table(engine)
    applied_versions = set(get_applied_migration_versions(engine))
    for migration in MIGRATIONS:
        if migration.version in applied_versions:
            continue
        sql_text = _load_migration_sql(migration.filename)
        with engine.begin() as connection:
            for statement in _split_sql_statements(sql_text):
                _execute_migration_statement(connection, statement)
            connection.execute(
                text(
                    """
                    INSERT OR IGNORE INTO schema_metadata (schema_version, created_at)
                    VALUES (:schema_version, :created_at)
                    """
                ),
                {
                    "schema_version": migration.version,
                    "created_at": datetime.now(UTC),
                },
            )


def get_applied_migration_versions(engine: Engine) -> list[str]:
    _ensure_schema_metadata_table(engine)
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT schema_version
                FROM schema_metadata
                ORDER BY schema_version ASC
                """
            )
        )
        return [str(row[0]) for row in rows]


def get_pending_migration_versions(engine: Engine) -> list[str]:
    applied = set(get_applied_migration_versions(engine))
    return [migration.version for migration in MIGRATIONS if migration.version not in applied]


def get_migration_status(database_url: str) -> dict[str, object]:
    _prepare_sqlite_path(database_url)
    engine = _create_database_engine(database_url)
    try:
        applied = get_applied_migration_versions(engine)
        pending = get_pending_migration_versions(engine)
        return {
            "current_version": applied[-1] if applied else None,
            "latest_version": LATEST_SCHEMA_VERSION,
            "applied_versions": applied,
            "pending_versions": pending,
        }
    finally:
        engine.dispose()


def _ensure_schema_metadata_table(engine: Engine) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schema_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schema_version VARCHAR(64) UNIQUE NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
    except OperationalError as exc:
        _raise_for_sqlite_lock(exc, engine.url)


def _migration_files_root() -> Path:
    return Path(__file__).resolve().parent / "migration_files"


def _load_migration_sql(filename: str) -> str:
    return (_migration_files_root() / filename).read_text(encoding="utf-8")


def _split_sql_statements(sql_text: str) -> list[str]:
    statements = [part.strip() for part in sql_text.split(";")]
    return [statement for statement in statements if statement]


def _execute_migration_statement(connection, statement: str) -> None:
    try:
        connection.execute(text(statement))
    except OperationalError as exc:
        message = str(exc).lower()
        if "duplicate column name" in message:
            return
        if "execution_logs" in message and "no such table" in message:
            return
        _raise_for_sqlite_lock(exc, connection.engine.url)
        raise


def _create_database_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite:///"):
        connect_args["timeout"] = SQLITE_BUSY_TIMEOUT_SECONDS
    return create_engine(database_url, future=True, connect_args=connect_args)


def _raise_for_sqlite_lock(exc: OperationalError, database_url: object) -> None:
    message = str(exc).lower()
    if "database is locked" not in message:
        return
    raise RuntimeError(
        f"Database is locked: {database_url}. Stop other LightClaw processes using the same SQLite file and retry."
    ) from exc
