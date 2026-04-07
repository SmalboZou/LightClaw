from abc import ABC, abstractmethod

from lightclaw.domain.jobs.models import JobDefinition


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
