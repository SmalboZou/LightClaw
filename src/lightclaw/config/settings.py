import os
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _read_dotenv(env_file: Path | None = None) -> dict[str, str]:
    env_file = env_file or Path(".env")
    if not env_file.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


class AppSettings(BaseModel):
    app_name: str = "LightClaw"
    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    provider_backend: Literal["mock", "openai_compatible", "anthropic"] = "mock"
    provider_model: str = "gpt-4o-mini"
    provider_base_url: str | None = None
    provider_api_key: str | None = None
    provider_extra_headers: dict[str, str] = {}
    storage_backend: Literal["memory", "sqlite"] = "sqlite"
    database_url: str | None = None
    tool_policy: Literal["read_only", "workspace_write"] = "workspace_write"
    allow_process_exec: bool = False
    allow_network_access: bool = False
    allowed_commands: list[str] = []
    workspace_root: Path = Path(".").resolve()
    max_agent_loops: int = 4
    provider_timeout_seconds: float = 15.0
    tool_timeout_seconds: float = 10.0
    scheduler_enabled: bool = False
    scheduler_poll_seconds: int = 30
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    console_admin_username: str | None = None
    console_admin_password: str | None = None
    console_secret_key: str = "lightclaw-dev-secret"
    skills_root: Path | None = None
    mcp_servers_root: Path | None = None

    def __init__(self, **data: object) -> None:
        env_file_override = data.pop("_env_file", None)
        resolved_env_file = Path(env_file_override) if env_file_override else Path(".env")
        prefer_file_values = env_file_override is not None
        file_values = _read_dotenv(resolved_env_file)

        def _value(name: str, default: str | None = None) -> str | None:
            if prefer_file_values and name in file_values:
                return file_values[name]
            if name in os.environ:
                return os.environ[name]
            if name in file_values:
                return file_values[name]
            return default

        merged = {
            "app_name": _value("LIGHTCLAW_APP_NAME", "LightClaw"),
            "env": _value("LIGHTCLAW_ENV", "development"),
            "log_level": _value("LIGHTCLAW_LOG_LEVEL", "INFO"),
            "provider_backend": _value("LIGHTCLAW_PROVIDER_BACKEND", "mock"),
            "provider_model": _value("LIGHTCLAW_PROVIDER_MODEL", "gpt-4o-mini"),
            "provider_base_url": _optional_text(_value("LIGHTCLAW_PROVIDER_BASE_URL")),
            "provider_api_key": _optional_text(_value("LIGHTCLAW_PROVIDER_API_KEY")),
            "provider_extra_headers": _load_json_dict(_value("LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON")),
            "storage_backend": _value("LIGHTCLAW_STORAGE_BACKEND", "sqlite"),
            "database_url": _optional_text(_value("LIGHTCLAW_DATABASE_URL")),
            "tool_policy": _value("LIGHTCLAW_TOOL_POLICY", "workspace_write"),
            "allow_process_exec": (_value("LIGHTCLAW_ALLOW_PROCESS_EXEC", "false") or "false").lower()
            == "true",
            "allow_network_access": (_value("LIGHTCLAW_ALLOW_NETWORK_ACCESS", "false") or "false").lower()
            == "true",
            "allowed_commands": [
                item.strip()
                for item in (_value("LIGHTCLAW_ALLOWED_COMMANDS", "") or "").split(",")
                if item.strip()
            ],
            "workspace_root": Path(
                _value("LIGHTCLAW_WORKSPACE_ROOT", str(Path(".").resolve()))
            ).resolve(),
            "max_agent_loops": int(_value("LIGHTCLAW_MAX_AGENT_LOOPS", "4") or "4"),
            "provider_timeout_seconds": float(
                _value("LIGHTCLAW_PROVIDER_TIMEOUT_SECONDS", "15") or "15"
            ),
            "tool_timeout_seconds": float(_value("LIGHTCLAW_TOOL_TIMEOUT_SECONDS", "10") or "10"),
            "scheduler_enabled": (_value("LIGHTCLAW_SCHEDULER_ENABLED", "false") or "false").lower()
            == "true",
            "scheduler_poll_seconds": int(_value("LIGHTCLAW_SCHEDULER_POLL_SECONDS", "30") or "30"),
            "telegram_bot_token": _optional_text(_value("LIGHTCLAW_TELEGRAM_BOT_TOKEN")),
            "telegram_webhook_secret": _optional_text(_value("LIGHTCLAW_TELEGRAM_WEBHOOK_SECRET")),
            "console_admin_username": _optional_text(_value("LIGHTCLAW_CONSOLE_ADMIN_USERNAME")),
            "console_admin_password": _optional_text(_value("LIGHTCLAW_CONSOLE_ADMIN_PASSWORD")),
            "console_secret_key": _value(
                "LIGHTCLAW_CONSOLE_SECRET_KEY",
                "lightclaw-dev-secret",
            ),
            "skills_root": _optional_text(_value("LIGHTCLAW_SKILLS_ROOT")),
            "mcp_servers_root": _optional_text(_value("LIGHTCLAW_MCP_SERVERS_ROOT")),
        }
        merged.update(data)
        super().__init__(**merged)

        if self.database_url is None:
            db_path = self.workspace_root / ".lightclaw" / "lightclaw.db"
            self.database_url = f"sqlite:///{db_path.as_posix()}"
        if self.skills_root is None:
            self.skills_root = (self.workspace_root / "skills").resolve()
        else:
            self.skills_root = Path(self.skills_root).resolve()
        if self.mcp_servers_root is None:
            self.mcp_servers_root = (self.workspace_root / "mcp" / "servers").resolve()
        else:
            self.mcp_servers_root = Path(self.mcp_servers_root).resolve()


def _load_json_dict(value: str | None) -> dict[str, str]:
    value = _optional_text(value)
    if value is None:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in parsed.items():
        if isinstance(key, str) and isinstance(item, str):
            normalized[key] = item
    return normalized
