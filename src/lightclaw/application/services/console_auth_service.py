import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from lightclaw.config.settings import AppSettings
from lightclaw.domain.errors import AuthenticationError, AuthorizationError
from lightclaw.infrastructure.persistence.models import ConsoleSessionRecord, ConsoleUserRecord


class ConsoleAuthService:
    SESSION_TTL = timedelta(days=7)

    def __init__(
        self,
        users_path: Path,
        settings: AppSettings,
        session_factory: sessionmaker | None = None,
    ) -> None:
        self._users_path = users_path
        self._settings = settings
        self._session_factory = session_factory
        self._sessions: dict[str, dict[str, str]] = {}
        self._bootstrap_from_settings()

    def setup_required(self) -> bool:
        return not self._load_users()

    def has_configured_provider(self) -> bool:
        if self._settings.provider_backend == "mock":
            return False
        if self._settings.provider_backend in {"openai_compatible", "anthropic"}:
            return bool(self._settings.provider_api_key and self._settings.provider_model)
        return True

    def get_setup_status(self) -> dict[str, object]:
        return {
            "setup_required": self.setup_required(),
            "has_users": not self.setup_required(),
            "has_provider_config": self.has_configured_provider(),
        }

    def bootstrap_admin(self, username: str, password: str) -> dict[str, str]:
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise AuthenticationError("Username and password are required.")
        users = self._load_users()
        if users:
            raise AuthenticationError("Console setup is already complete.")
        user = self._build_user(username=username, password=password, role="admin")
        self._save_users([user])
        return {"username": username, "role": "admin"}

    def login(self, username: str, password: str) -> tuple[str, dict[str, str]]:
        user = self._find_user(username)
        if user is None or not self._verify_password(password, user["password_hash"]):
            raise AuthenticationError("Invalid username or password.")
        token = secrets.token_urlsafe(24)
        if self._session_factory is not None:
            expires_at = datetime.now(UTC) + self.SESSION_TTL
            with self._session_factory() as session:
                session.add(
                    ConsoleSessionRecord(
                        session_token=token,
                        username=user["username"],
                        role=user["role"],
                        expires_at=expires_at,
                    )
                )
                session.commit()
        else:
            self._sessions[token] = {"username": user["username"], "role": user["role"]}
        return token, {"username": user["username"], "role": user["role"]}

    def logout(self, token: str | None) -> None:
        if token:
            if self._session_factory is not None:
                with self._session_factory() as session:
                    session.execute(
                        delete(ConsoleSessionRecord).where(ConsoleSessionRecord.session_token == token)
                    )
                    session.commit()
            else:
                self._sessions.pop(token, None)

    def resolve_session(self, token: str | None) -> dict[str, str]:
        if not token:
            raise AuthenticationError("Login required.")
        if self._session_factory is not None:
            with self._session_factory() as session:
                row = session.execute(
                    select(ConsoleSessionRecord).where(ConsoleSessionRecord.session_token == token)
                ).scalar_one_or_none()
                expires_at = _coerce_utc_datetime(row.expires_at) if row is not None else None
                if row is None or expires_at < datetime.now(UTC):
                    if row is not None:
                        session.delete(row)
                        session.commit()
                    raise AuthenticationError("Session expired. Please login again.")
                return {"username": row.username, "role": row.role}
        session = self._sessions.get(token)
        if session is None:
            raise AuthenticationError("Session expired. Please login again.")
        return dict(session)

    def list_users(self, actor: dict[str, str]) -> list[dict[str, str]]:
        self._require_admin(actor)
        return [
            {
                "username": user["username"],
                "role": user["role"],
                "created_at": user["created_at"],
            }
            for user in self._load_users()
        ]

    def create_user(
        self,
        actor: dict[str, str],
        username: str,
        password: str,
        role: str = "operator",
    ) -> dict[str, str]:
        self._require_admin(actor)
        users = self._load_users()
        normalized_username = username.strip()
        if not normalized_username or not password.strip():
            raise AuthenticationError("Username and password are required.")
        if any(user["username"] == normalized_username for user in users):
            raise AuthenticationError(f"User '{normalized_username}' already exists.")
        user = self._build_user(username=normalized_username, password=password, role=role)
        users.append(user)
        self._save_users(users)
        return {
            "username": normalized_username,
            "role": role,
        }

    def update_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        self._bootstrap_from_settings()

    def _bootstrap_from_settings(self) -> None:
        if self._load_users():
            return
        if self._settings.console_admin_username and self._settings.console_admin_password:
            user = self._build_user(
                username=self._settings.console_admin_username,
                password=self._settings.console_admin_password,
                role="admin",
            )
            self._save_users([user])

    def _build_user(self, username: str, password: str, role: str) -> dict[str, str]:
        return {
            "username": username,
            "role": role,
            "password_hash": self._hash_password(password),
            "created_at": datetime.now(UTC).isoformat(),
        }

    def _find_user(self, username: str) -> dict[str, str] | None:
        for user in self._load_users():
            if user["username"] == username.strip():
                return user
        return None

    def _load_users(self) -> list[dict[str, str]]:
        if self._session_factory is not None:
            with self._session_factory() as session:
                rows = session.execute(
                    select(ConsoleUserRecord).order_by(ConsoleUserRecord.id.asc())
                ).scalars()
                return [
                    {
                        "username": row.username,
                        "role": row.role,
                        "password_hash": row.password_hash,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ]
        if not self._users_path.exists():
            return []
        payload = json.loads(self._users_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _save_users(self, users: list[dict[str, str]]) -> None:
        if self._session_factory is not None:
            with self._session_factory() as session:
                session.execute(delete(ConsoleUserRecord))
                for user in users:
                    session.add(
                        ConsoleUserRecord(
                            username=user["username"],
                            role=user["role"],
                            password_hash=user["password_hash"],
                            created_at=datetime.fromisoformat(user["created_at"]),
                        )
                    )
                session.commit()
            return
        self._users_path.parent.mkdir(parents=True, exist_ok=True)
        self._users_path.write_text(json.dumps(users, indent=2), encoding="utf-8")

    def _hash_password(self, password: str) -> str:
        digest = hmac.new(
            self._settings.console_secret_key.encode("utf-8"),
            password.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest

    def _verify_password(self, password: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self._hash_password(password), expected_hash)

    def _require_admin(self, actor: dict[str, str]) -> None:
        if actor.get("role") != "admin":
            raise AuthorizationError("Admin access is required for this action.")


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
