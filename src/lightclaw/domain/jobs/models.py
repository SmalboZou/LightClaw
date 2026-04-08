from datetime import UTC, datetime

from pydantic import BaseModel, Field


class JobDefinition(BaseModel):
    job_id: str
    name: str
    cron: str
    enabled: bool = True
    input_prompt: str
    target_channel: str
    target_destination: str | None = None
    skills: list[str] = Field(default_factory=list)
    policy_mode: str = "workspace_write"
    last_status: str | None = None
    last_run_at: datetime | None = None
    last_output: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobRun(BaseModel):
    run_id: str
    job_id: str
    trigger: str = "manual"
    status: str
    input_prompt: str
    output_text: str | None = None
    error_message: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
