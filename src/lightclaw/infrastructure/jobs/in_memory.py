from lightclaw.domain.jobs.base import JobStore
from lightclaw.domain.jobs.models import JobDefinition, JobRun


class InMemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._jobs: dict[str, JobDefinition] = {}
        self._job_runs: list[JobRun] = []

    async def upsert_job(self, job: JobDefinition) -> None:
        self._jobs[job.job_id] = job

    async def get_job(self, job_id: str) -> JobDefinition | None:
        return self._jobs.get(job_id)

    async def list_jobs(self) -> list[JobDefinition]:
        return list(self._jobs.values())

    async def record_job_run(self, job_run: JobRun) -> None:
        self._job_runs.append(job_run)

    async def list_job_runs(self, job_id: str | None = None) -> list[JobRun]:
        if job_id is None:
            return list(self._job_runs)
        return [job_run for job_run in self._job_runs if job_run.job_id == job_id]

    async def get_job_run(self, run_id: str) -> JobRun | None:
        for job_run in self._job_runs:
            if job_run.run_id == run_id:
                return job_run
        return None
