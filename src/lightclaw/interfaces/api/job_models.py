from datetime import datetime

from pydantic import BaseModel, Field


class JobPayload(BaseModel):
    job_id: str
    name: str
    cron: str
    enabled: bool = True
    input_prompt: str = Field(min_length=1)
    target_channel: str = "scheduler"
    target_destination: str | None = None
    skills: list[str] = Field(default_factory=list)
    policy_mode: str = "workspace_write"


class JobResponse(BaseModel):
    job_id: str
    name: str
    cron: str
    enabled: bool
    input_prompt: str
    target_channel: str
    target_destination: str | None = None
    skills: list[str] = Field(default_factory=list)
    policy_mode: str
    last_status: str | None = None
    last_run_at: datetime | None = None
    last_output: str | None = None


class JobTriggerResponse(BaseModel):
    job_id: str
    status: str
    last_output: str | None = None


class SchedulerStatusResponse(BaseModel):
    running: bool
    poll_seconds: int
    last_tick_key: str | None = None
