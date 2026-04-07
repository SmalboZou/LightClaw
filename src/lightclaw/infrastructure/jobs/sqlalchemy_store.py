import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from lightclaw.domain.jobs.base import JobStore
from lightclaw.domain.jobs.models import JobDefinition
from lightclaw.infrastructure.persistence.models import JobRecord


class SqlAlchemyJobStore(JobStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    async def upsert_job(self, job: JobDefinition) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(JobRecord).where(JobRecord.job_id == job.job_id)
            ).scalar_one_or_none()
            if existing is None:
                existing = JobRecord(job_id=job.job_id)
                session.add(existing)

            existing.name = job.name
            existing.cron = job.cron
            existing.enabled = job.enabled
            existing.input_prompt = job.input_prompt
            existing.target_channel = job.target_channel
            existing.target_destination = job.target_destination
            existing.skills = json.dumps(job.skills)
            existing.policy_mode = job.policy_mode
            existing.last_status = job.last_status
            existing.last_run_at = job.last_run_at
            existing.last_output = job.last_output
            existing.created_at = job.created_at
            existing.updated_at = datetime.now(UTC)
            session.commit()

    async def get_job(self, job_id: str) -> JobDefinition | None:
        with self._session_factory() as session:
            row = session.execute(
                select(JobRecord).where(JobRecord.job_id == job_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_model(row)

    async def list_jobs(self) -> list[JobDefinition]:
        with self._session_factory() as session:
            rows = session.execute(select(JobRecord).order_by(JobRecord.id.asc())).scalars()
            return [self._to_model(row) for row in rows]

    def _to_model(self, row: JobRecord) -> JobDefinition:
        return JobDefinition(
            job_id=row.job_id,
            name=row.name,
            cron=row.cron,
            enabled=row.enabled,
            input_prompt=row.input_prompt,
            target_channel=row.target_channel,
            target_destination=row.target_destination,
            skills=json.loads(row.skills or "[]"),
            policy_mode=row.policy_mode,
            last_status=row.last_status,
            last_run_at=row.last_run_at,
            last_output=row.last_output,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
