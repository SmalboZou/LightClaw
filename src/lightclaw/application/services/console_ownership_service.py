import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from lightclaw.domain.errors import AuthorizationError
from lightclaw.infrastructure.persistence.models import ConsoleOwnershipRecord


class ConsoleOwnershipService:
    def __init__(self, metadata_path: Path, session_factory: sessionmaker | None = None) -> None:
        self._metadata_path = metadata_path
        self._session_factory = session_factory

    def list_owned_sessions(self, session_ids: list[str], username: str) -> list[str]:
        return self._list_owned("session", session_ids, username)

    def ensure_session_access(self, session_id: str, username: str) -> None:
        self._ensure_access("session", session_id, username)

    def claim_session(self, session_id: str, username: str) -> None:
        self._claim("session", session_id, username)

    def list_owned_jobs(self, job_ids: list[str], username: str) -> list[str]:
        return self._list_owned("job", job_ids, username)

    def ensure_job_access(self, job_id: str, username: str) -> None:
        self._ensure_access("job", job_id, username)

    def claim_job(self, job_id: str, username: str) -> None:
        self._claim("job", job_id, username)

    def _list_owned(self, resource_type: str, resource_ids: list[str], username: str) -> list[str]:
        payload = self._load()
        return [
            resource_id
            for resource_id in resource_ids
            if payload[f"{resource_type}s"].get(resource_id) == username
        ]

    def _ensure_access(self, resource_type: str, resource_id: str, username: str) -> None:
        owner = self._load()[f"{resource_type}s"].get(resource_id)
        if owner is None:
            return
        if owner != username:
            raise AuthorizationError(f"This {resource_type} belongs to another user.")

    def _claim(self, resource_type: str, resource_id: str, username: str) -> None:
        payload = self._load()
        owner = payload[f"{resource_type}s"].get(resource_id)
        if owner and owner != username:
            raise AuthorizationError(f"This {resource_type} belongs to another user.")
        payload[f"{resource_type}s"][resource_id] = username
        self._save(payload)

    def _load(self) -> dict[str, dict[str, str]]:
        if self._session_factory is not None:
            with self._session_factory() as session:
                rows = session.execute(
                    select(ConsoleOwnershipRecord).order_by(ConsoleOwnershipRecord.id.asc())
                ).scalars()
                payload = {"sessions": {}, "jobs": {}}
                for row in rows:
                    if row.resource_type == "session":
                        payload["sessions"][row.resource_id] = row.username
                    elif row.resource_type == "job":
                        payload["jobs"][row.resource_id] = row.username
                return payload
        if not self._metadata_path.exists():
            return {"sessions": {}, "jobs": {}}
        payload = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"sessions": {}, "jobs": {}}
        return {
            "sessions": dict(payload.get("sessions", {})),
            "jobs": dict(payload.get("jobs", {})),
        }

    def _save(self, payload: dict[str, dict[str, str]]) -> None:
        if self._session_factory is not None:
            with self._session_factory() as session:
                session.execute(delete(ConsoleOwnershipRecord))
                for resource_id, username in payload["sessions"].items():
                    session.add(
                        ConsoleOwnershipRecord(
                            resource_type="session",
                            resource_id=resource_id,
                            username=username,
                        )
                    )
                for resource_id, username in payload["jobs"].items():
                    session.add(
                        ConsoleOwnershipRecord(
                            resource_type="job",
                            resource_id=resource_id,
                            username=username,
                        )
                    )
                session.commit()
            return
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
