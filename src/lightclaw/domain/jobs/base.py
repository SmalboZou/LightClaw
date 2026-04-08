from abc import ABC, abstractmethod

from lightclaw.domain.jobs.models import JobDefinition, JobRun


class JobStore(ABC):
    @abstractmethod
    async def upsert_job(self, job: JobDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_job(self, job_id: str) -> JobDefinition | None:
        raise NotImplementedError

    @abstractmethod
    async def list_jobs(self) -> list[JobDefinition]:
        raise NotImplementedError

    @abstractmethod
    async def record_job_run(self, job_run: JobRun) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_job_runs(self, job_id: str | None = None) -> list[JobRun]:
        raise NotImplementedError

    @abstractmethod
    async def get_job_run(self, run_id: str) -> JobRun | None:
        raise NotImplementedError
