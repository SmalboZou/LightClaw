from pathlib import Path
import json

from lightclaw.config.settings import AppSettings


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

    def __init__(self, env_path: Path, settings: AppSettings) -> None:
        self._env_path = env_path
        self._settings = settings

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
        requires_restart = next_storage_backend != self._settings.storage_backend
        return {
            "saved": True,
            "requires_restart": requires_restart,
            "updated_keys": sorted(updates.keys()),
        }

    def _read_env_lines(self) -> list[str]:
        if not self._env_path.exists():
            return []
        return self._env_path.read_text(encoding="utf-8").splitlines()


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
