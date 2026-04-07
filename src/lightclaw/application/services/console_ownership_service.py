import json
from pathlib import Path

from lightclaw.domain.errors import AuthorizationError


class ConsoleOwnershipService:
    def __init__(self, metadata_path: Path) -> None:
        self._metadata_path = metadata_path

    def list_owned_sessions(self, session_ids: list[str], username: str) -> list[str]:
        payload = self._load()
        return [
            session_id
            for session_id in session_ids
            if payload["sessions"].get(session_id) == username
        ]

    def ensure_session_access(self, session_id: str, username: str) -> None:
        owner = self._load()["sessions"].get(session_id)
        if owner is None:
            return
        if owner != username:
            raise AuthorizationError("This session belongs to another user.")

    def claim_session(self, session_id: str, username: str) -> None:
        payload = self._load()
        owner = payload["sessions"].get(session_id)
        if owner and owner != username:
            raise AuthorizationError("This session belongs to another user.")
        payload["sessions"][session_id] = username
        self._save(payload)

    def list_owned_jobs(self, job_ids: list[str], username: str) -> list[str]:
        payload = self._load()
        return [job_id for job_id in job_ids if payload["jobs"].get(job_id) == username]

    def ensure_job_access(self, job_id: str, username: str) -> None:
        owner = self._load()["jobs"].get(job_id)
        if owner is None:
            return
        if owner != username:
            raise AuthorizationError("This job belongs to another user.")

    def claim_job(self, job_id: str, username: str) -> None:
        payload = self._load()
        owner = payload["jobs"].get(job_id)
        if owner and owner != username:
            raise AuthorizationError("This job belongs to another user.")
        payload["jobs"][job_id] = username
        self._save(payload)

    def _load(self) -> dict[str, dict[str, str]]:
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
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
