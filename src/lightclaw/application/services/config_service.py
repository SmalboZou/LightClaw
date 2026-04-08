from pathlib import Path
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from lightclaw.config.settings import AppSettings
from lightclaw.infrastructure.persistence.database import create_session_factory
from lightclaw.infrastructure.persistence.models import RuntimeConfigRecord, RuntimeStateRecord


class ConfigService:
    MANAGED_KEYS = [
        "LIGHTCLAW_PROVIDER_BACKEND",
        "LIGHTCLAW_PROVIDER_MODEL",
        "LIGHTCLAW_PROVIDER_BASE_URL",
        "LIGHTCLAW_PROVIDER_API_KEY",
        "LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON",
        "LIGHTCLAW_STORAGE_BACKEND",
        "LIGHTCLAW_TOOL_POLICY",
        "LIGHTCLAW_ALLOW_PROCESS_EXEC",
        "LIGHTCLAW_ALLOW_NETWORK_ACCESS",
        "LIGHTCLAW_CONSOLE_ADMIN_USERNAME",
        "LIGHTCLAW_CONSOLE_ADMIN_PASSWORD",
    ]

    SECRET_KEYS = {"LIGHTCLAW_PROVIDER_API_KEY", "LIGHTCLAW_CONSOLE_ADMIN_PASSWORD"}
    SETTINGS_KEY_MAP = {
        "LIGHTCLAW_PROVIDER_BACKEND": "provider_backend",
        "LIGHTCLAW_PROVIDER_MODEL": "provider_model",
        "LIGHTCLAW_PROVIDER_BASE_URL": "provider_base_url",
        "LIGHTCLAW_PROVIDER_API_KEY": "provider_api_key",
        "LIGHTCLAW_STORAGE_BACKEND": "storage_backend",
        "LIGHTCLAW_TOOL_POLICY": "tool_policy",
        "LIGHTCLAW_ALLOW_PROCESS_EXEC": "allow_process_exec",
        "LIGHTCLAW_ALLOW_NETWORK_ACCESS": "allow_network_access",
        "LIGHTCLAW_CONSOLE_ADMIN_USERNAME": "console_admin_username",
        "LIGHTCLAW_CONSOLE_ADMIN_PASSWORD": "console_admin_password",
    }

    def __init__(
        self,
        env_path: Path,
        settings: AppSettings,
        session_factory: sessionmaker | None = None,
    ) -> None:
        self._env_path = env_path
        self._settings = settings
        self._session_factory = session_factory
        self._runtime_state_path = settings.workspace_root / ".lightclaw" / "runtime_state.json"

    async def get_console_config(self) -> dict[str, object]:
        return {
            "provider_backend": self._settings.provider_backend,
            "provider_model": self._settings.provider_model,
            "provider_base_url": self._settings.provider_base_url,
            "provider_api_key_masked": _mask_secret(self._settings.provider_api_key),
            "has_provider_api_key": bool(self._settings.provider_api_key),
            "provider_extra_headers_json": json.dumps(
                self._settings.provider_extra_headers,
                indent=2,
                ensure_ascii=True,
            ) if self._settings.provider_extra_headers else "",
            "storage_backend": self._settings.storage_backend,
            "tool_policy": self._settings.tool_policy,
            "allow_process_exec": self._settings.allow_process_exec,
            "allow_network_access": self._settings.allow_network_access,
            "workspace_root": str(self._settings.workspace_root),
            "skills_root": str(self._settings.skills_root),
            "mcp_servers_root": str(self._settings.mcp_servers_root),
            "console_admin_username": self._settings.console_admin_username,
            "requires_restart": False,
        }

    async def get_runtime_status(self) -> dict[str, object]:
        payload = self._load_runtime_state()
        last_applied_at = payload.get("last_applied_at")
        last_reload_reason = payload.get("last_reload_reason")
        desired_config = self._load_runtime_config_values()
        active_config = {
            "provider_backend": self._settings.provider_backend,
            "provider_model": self._settings.provider_model,
            "provider_base_url": self._settings.provider_base_url,
            "storage_backend": self._settings.storage_backend,
            "tool_policy": self._settings.tool_policy,
            "allow_process_exec": self._settings.allow_process_exec,
            "allow_network_access": self._settings.allow_network_access,
        }
        desired_summary = {
            "provider_backend": desired_config.get("LIGHTCLAW_PROVIDER_BACKEND", active_config["provider_backend"]),
            "provider_model": desired_config.get("LIGHTCLAW_PROVIDER_MODEL", active_config["provider_model"]),
            "provider_base_url": _normalize_optional_text(
                desired_config.get("LIGHTCLAW_PROVIDER_BASE_URL", active_config["provider_base_url"])
            ),
            "storage_backend": desired_config.get("LIGHTCLAW_STORAGE_BACKEND", active_config["storage_backend"]),
            "tool_policy": desired_config.get("LIGHTCLAW_TOOL_POLICY", active_config["tool_policy"]),
            "allow_process_exec": desired_config.get("LIGHTCLAW_ALLOW_PROCESS_EXEC", str(active_config["allow_process_exec"]).lower()) == "true",
            "allow_network_access": desired_config.get("LIGHTCLAW_ALLOW_NETWORK_ACCESS", str(active_config["allow_network_access"]).lower()) == "true",
        }
        desired_matches_active = desired_summary == active_config
        return {
            "active": active_config,
            "desired": desired_summary,
            "desired_matches_active": desired_matches_active,
            "last_applied_at": last_applied_at,
            "last_reload_reason": last_reload_reason,
        }

    async def save_console_config(self, payload: dict[str, object]) -> dict[str, object]:
        env_lines = self._read_env_lines()
        provider_api_key = str(payload.get("provider_api_key") or "").strip()
        provider_extra_headers_json = str(payload.get("provider_extra_headers_json") or "").strip()
        provider_extra_headers = _normalize_headers_json(provider_extra_headers_json)
        next_storage_backend = str(payload.get("storage_backend") or "sqlite")
        updates = {
            "LIGHTCLAW_PROVIDER_BACKEND": str(payload.get("provider_backend") or "mock"),
            "LIGHTCLAW_PROVIDER_MODEL": str(payload.get("provider_model") or "gpt-4o-mini"),
            "LIGHTCLAW_PROVIDER_BASE_URL": str(payload.get("provider_base_url") or ""),
            "LIGHTCLAW_PROVIDER_API_KEY": provider_api_key or str(self._settings.provider_api_key or ""),
            "LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON": provider_extra_headers,
            "LIGHTCLAW_STORAGE_BACKEND": next_storage_backend,
            "LIGHTCLAW_TOOL_POLICY": str(payload.get("tool_policy") or "workspace_write"),
            "LIGHTCLAW_ALLOW_PROCESS_EXEC": str(
                bool(payload.get("allow_process_exec", False))
            ).lower(),
            "LIGHTCLAW_ALLOW_NETWORK_ACCESS": str(
                bool(payload.get("allow_network_access", False))
            ).lower(),
            "LIGHTCLAW_CONSOLE_ADMIN_USERNAME": str(
                payload.get("console_admin_username") or self._settings.console_admin_username or ""
            ),
            "LIGHTCLAW_CONSOLE_ADMIN_PASSWORD": str(
                payload.get("console_admin_password") or self._settings.console_admin_password or ""
            ),
        }
        rewritten = _rewrite_env(env_lines, updates)
        self._env_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
        self._persist_runtime_config(updates)
        requires_restart = next_storage_backend != self._settings.storage_backend
        return {
            "saved": True,
            "requires_restart": requires_restart,
            "updated_keys": sorted(updates.keys()),
        }

    def record_runtime_applied(self, settings: AppSettings, reason: str) -> None:
        payload = {
            "last_applied_at": datetime.now(UTC).isoformat(),
            "last_reload_reason": reason,
            "provider_backend": settings.provider_backend,
            "provider_model": settings.provider_model,
            "provider_base_url": settings.provider_base_url or "",
            "storage_backend": settings.storage_backend,
            "tool_policy": settings.tool_policy,
        }
        if self._session_factory is not None:
            with self._session_factory() as session:
                for key, value in payload.items():
                    row = session.execute(
                        select(RuntimeStateRecord).where(RuntimeStateRecord.state_key == key)
                    ).scalar_one_or_none()
                    if row is None:
                        row = RuntimeStateRecord(state_key=key)
                        session.add(row)
                    row.state_value = str(value)
                    row.updated_at = datetime.now(UTC)
                session.commit()
            return
        self._runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._runtime_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_env_lines(self) -> list[str]:
        if not self._env_path.exists():
            return []
        return self._env_path.read_text(encoding="utf-8").splitlines()

    def _persist_runtime_config(self, updates: dict[str, str]) -> None:
        if self._session_factory is None:
            return
        with self._session_factory() as session:
            for key, value in updates.items():
                row = session.execute(
                    select(RuntimeConfigRecord).where(RuntimeConfigRecord.config_key == key)
                ).scalar_one_or_none()
                if row is None:
                    row = RuntimeConfigRecord(config_key=key)
                    session.add(row)
                row.config_value = value
                row.is_secret = key in self.SECRET_KEYS
                row.updated_at = datetime.now(UTC)
            session.commit()

    def _load_runtime_config_values(self) -> dict[str, str]:
        if self._session_factory is not None:
            with self._session_factory() as session:
                rows = session.execute(
                    select(RuntimeConfigRecord).order_by(RuntimeConfigRecord.id.asc())
                ).scalars()
                return {row.config_key: row.config_value for row in rows}
        env_lines = self._read_env_lines()
        payload: dict[str, str] = {}
        for line in env_lines:
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            payload[key.strip()] = value.strip()
        return payload

    def _load_runtime_state(self) -> dict[str, str]:
        if self._session_factory is not None:
            with self._session_factory() as session:
                rows = session.execute(
                    select(RuntimeStateRecord).order_by(RuntimeStateRecord.id.asc())
                ).scalars()
                return {row.state_key: row.state_value for row in rows}
        if not self._runtime_state_path.exists():
            return {}
        payload = json.loads(self._runtime_state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items()}


def _rewrite_env(lines: list[str], updates: dict[str, str]) -> list[str]:
    rewritten: list[str] = []
    remaining = dict(updates)
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            rewritten.append(line)
            continue
        key, _value = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in remaining:
            rewritten.append(f"{normalized_key}={remaining.pop(normalized_key)}")
        else:
            rewritten.append(line)
    for key in ConfigService.MANAGED_KEYS:
        if key in remaining:
            rewritten.append(f"{key}={remaining.pop(key)}")
    for key, value in remaining.items():
        rewritten.append(f"{key}={value}")
    return rewritten


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _normalize_headers_json(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    normalized = {
        str(key): str(item)
        for key, item in parsed.items()
        if isinstance(key, str) and isinstance(item, str)
    }
    return json.dumps(normalized, ensure_ascii=True)


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def hydrate_settings_from_runtime_config(settings: AppSettings) -> AppSettings:
    if settings.storage_backend != "sqlite":
        return settings
    session_factory = create_session_factory(settings.database_url)
    with session_factory() as session:
        rows = session.execute(
            select(RuntimeConfigRecord).order_by(RuntimeConfigRecord.id.asc())
        ).scalars()
        values = {row.config_key: row.config_value for row in rows}
    if not values:
        return settings

    overrides: dict[str, object] = {
        "workspace_root": settings.workspace_root,
        "database_url": settings.database_url,
        "skills_root": settings.skills_root,
        "mcp_servers_root": settings.mcp_servers_root,
        "app_name": settings.app_name,
        "env": settings.env,
        "log_level": settings.log_level,
        "allowed_commands": settings.allowed_commands,
        "max_agent_loops": settings.max_agent_loops,
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "tool_timeout_seconds": settings.tool_timeout_seconds,
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduler_poll_seconds": settings.scheduler_poll_seconds,
        "telegram_bot_token": settings.telegram_bot_token,
        "telegram_webhook_secret": settings.telegram_webhook_secret,
        "console_secret_key": settings.console_secret_key,
    }
    for env_key, setting_key in ConfigService.SETTINGS_KEY_MAP.items():
        if env_key not in values:
            continue
        raw_value = values[env_key]
        if setting_key in {"allow_process_exec", "allow_network_access"}:
            overrides[setting_key] = raw_value.lower() == "true"
        elif setting_key in {"provider_base_url", "provider_api_key", "console_admin_username", "console_admin_password"}:
            overrides[setting_key] = _normalize_optional_text(raw_value)
        else:
            overrides[setting_key] = raw_value
    if "LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON" in values:
        overrides["provider_extra_headers"] = _parse_headers_json(values["LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON"])
    return AppSettings(**overrides)


def _parse_headers_json(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in payload.items()
        if isinstance(key, str) and isinstance(item, str)
    }
