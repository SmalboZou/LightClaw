from lightclaw.domain.jobs.base import JobStore
from lightclaw.domain.jobs.models import JobDefinition


class InMemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._jobs: dict[str, JobDefinition] = {}

    async def upsert_job(self, job: JobDefinition) -> None:
        self._jobs[job.job_id] = job

    async def get_job(self, job_id: str) -> JobDefinition | None:
        return self._jobs.get(job_id)

    async def list_jobs(self) -> list[JobDefinition]:
        return list(self._jobs.values())
