from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent.parent
TMP_DIR = WORKSPACE / ".lightclaw" / "tmp"
UV_CACHE_DIR = WORKSPACE / ".lightclaw" / "uv-cache"
VENV_DIR = WORKSPACE / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
ENV_FILE = WORKSPACE / ".env"
ENV_EXAMPLE_FILE = WORKSPACE / ".env.example"
UV_LOCK_FILE = WORKSPACE / "uv.lock"
MIGRATIONS_DIR = WORKSPACE / "src" / "lightclaw" / "infrastructure" / "persistence" / "migration_files"


def resolve_bootstrap_python() -> Path:
    preferred = [
        Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python312" / "python.exe",
        Path(r"D:\Anaconda\anaconda\python.exe"),
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    if Path(sys.executable).exists():
        return Path(sys.executable)
    raise RuntimeError("Unable to find a bootstrap Python interpreter.")


def venv_needs_rebuild(venv_dir: Path, bootstrap_python: Path) -> bool:
    cfg_path = venv_dir / "pyvenv.cfg"
    if not cfg_path.exists():
        return False
    cfg_text = cfg_path.read_text(encoding="utf-8")
    bootstrap_home = str(bootstrap_python.parent)
    if "home = D:\\Anaconda\\anaconda" in cfg_text:
        return True
    for line in cfg_text.splitlines():
        if line.startswith("home = "):
            venv_home = line.removeprefix("home = ").strip()
            return bool(venv_home and venv_home != bootstrap_home)
    return False


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    UV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(TMP_DIR)
    env["TMP"] = str(TMP_DIR)
    env["UV_CACHE_DIR"] = str(UV_CACHE_DIR)
    env["PYTHONPATH"] = str((WORKSPACE / "src").resolve())
    return env


def read_dotenv() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def resolve_database_url() -> str:
    env_values = read_dotenv()
    database_url = env_values.get("LIGHTCLAW_DATABASE_URL", "").strip()
    if database_url:
        return database_url
    return f"sqlite:///{(WORKSPACE / '.lightclaw' / 'lightclaw.db').as_posix()}"


def apply_sqlite_migrations(database_url: str) -> tuple[str | None, list[str]]:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError(f"Unsupported database URL for local bootstrap: {database_url}")
    db_path = Path(database_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_version VARCHAR(64) UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT schema_version FROM schema_metadata ORDER BY schema_version ASC"
            ).fetchall()
        }
        migration_versions: list[str] = []
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = migration_path.stem
            migration_versions.append(version)
            if version in applied:
                continue
            sql_text = migration_path.read_text(encoding="utf-8")
            statements = [part.strip() for part in sql_text.split(";") if part.strip()]
            for statement in statements:
                try:
                    connection.execute(statement)
                except sqlite3.OperationalError as exc:
                    message = str(exc).lower()
                    if "duplicate column name" in message:
                        continue
                    if "execution_logs" in message and "no such table" in message:
                        continue
                    raise
            connection.execute(
                """
                INSERT OR IGNORE INTO schema_metadata (schema_version, created_at)
                VALUES (?, ?)
                """,
                (version, datetime.now(UTC).isoformat()),
            )
            connection.commit()

        applied_rows = connection.execute(
            "SELECT schema_version FROM schema_metadata ORDER BY schema_version ASC"
        ).fetchall()
        applied_versions = [str(row[0]) for row in applied_rows]
    return (applied_versions[-1] if applied_versions else None, migration_versions)


def run(command: list[str], env: dict[str, str]) -> None:
    completed = subprocess.run(command, cwd=WORKSPACE, env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def main() -> int:
    env = build_env()
    bootstrap_python = resolve_bootstrap_python()

    if not ENV_FILE.exists() and ENV_EXAMPLE_FILE.exists():
        shutil.copyfile(ENV_EXAMPLE_FILE, ENV_FILE)

    if VENV_PYTHON.exists() and venv_needs_rebuild(VENV_DIR, bootstrap_python):
        print(f"[1/3] Rebuilding .venv with bootstrap Python: {bootstrap_python}", flush=True)
        shutil.rmtree(VENV_DIR)

    if not VENV_PYTHON.exists():
        print("[1/3] Creating virtual environment with bootstrap Python...", flush=True)
        run([str(bootstrap_python), "-m", "venv", str(VENV_DIR)], env)

    if not UV_LOCK_FILE.exists():
        print("[2/3] Generating uv.lock...", flush=True)
        run([str(bootstrap_python), "-m", "uv", "lock"], env)

    print("[2/3] Syncing dependencies into .venv...", flush=True)
    run(
        [
            str(bootstrap_python),
            "-m",
            "uv",
            "sync",
            "--extra",
            "dev",
            "--no-install-project",
            "--locked",
            "--quiet",
        ],
        env,
    )

    print("[3/3] Applying database migrations...", flush=True)
    database_url = resolve_database_url()
    current_version, migration_versions = apply_sqlite_migrations(database_url)
    print("database_url=" + database_url, flush=True)
    print("current_version=" + str(current_version), flush=True)
    print("pending_versions=none", flush=True)
    print("Development environment initialized with uv-managed .venv.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
