import asyncio
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.jobs.models import JobDefinition
from lightclaw.interfaces.api.app import create_api

ROOT = Path(__file__).resolve().parents[1]


def _make_test_workspace() -> Path:
    workspace = Path("tests/.tmp") / str(uuid.uuid4())
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def test_job_service_runs_persisted_job() -> None:
    workspace = _make_test_workspace()
    settings = AppSettings(
        storage_backend="sqlite",
        database_url=f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}",
        workspace_root=workspace,
    )

    try:
        container = build_container(settings)
        asyncio.run(
            container.job_service.upsert_job(
                JobDefinition(
                    job_id="job-1",
                    name="Daily Summary",
                    cron="* * * * *",
                    input_prompt="hello scheduled job",
                    target_channel="scheduler",
                )
            )
        )

        result = asyncio.run(container.job_service.run_job("job-1"))
        assert result.last_status == "completed"
        assert "hello scheduled job" in (result.last_output or "")

        stored = asyncio.run(container.job_service.get_job("job-1"))
        assert stored is not None
        assert stored.last_status == "completed"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_job_service_passes_skills_to_chat_execution() -> None:
    workspace = _make_test_workspace()
    settings = AppSettings(
        storage_backend="memory",
        workspace_root=workspace,
        skills_root=ROOT / "skills",
    )
    try:
        container = build_container(settings)
        asyncio.run(
            container.job_service.upsert_job(
                JobDefinition(
                    job_id="skilled-job",
                    name="Skilled Job",
                    cron="* * * * *",
                    input_prompt="hello scheduled job",
                    target_channel="scheduler",
                    skills=["writing_assistant"],
                )
            )
        )

        result = asyncio.run(container.job_service.run_job("skilled-job"))
        assert result.last_status == "completed"
        assert "instructions=1" in (result.last_output or "")
        assert result.skills == ["writing_assistant"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_scheduler_runs_due_jobs() -> None:
    workspace = _make_test_workspace()
    settings = AppSettings(storage_backend="memory", workspace_root=workspace)
    try:
        container = build_container(settings)
        asyncio.run(
            container.job_service.upsert_job(
                JobDefinition(
                    job_id="due-job",
                    name="Due Job",
                    cron="5 9 * * *",
                    input_prompt="run me now",
                    target_channel="scheduler",
                )
            )
        )

        executed = asyncio.run(
            container.scheduler_service.run_due_jobs(datetime(2026, 4, 7, 9, 5, tzinfo=UTC))
        )
        assert len(executed) == 1
        assert executed[0].job_id == "due-job"
        assert executed[0].last_status == "completed"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_scheduler_tick_deduplicates_same_minute() -> None:
    workspace = _make_test_workspace()
    settings = AppSettings(storage_backend="memory", workspace_root=workspace)
    try:
        container = build_container(settings)
        asyncio.run(
            container.job_service.upsert_job(
                JobDefinition(
                    job_id="tick-job",
                    name="Tick Job",
                    cron="10 8 * * *",
                    input_prompt="tick me",
                    target_channel="scheduler",
                )
            )
        )
        now = datetime(2026, 4, 7, 8, 10, tzinfo=UTC)
        first = asyncio.run(container.scheduler_service.run_pending_tick(now))
        second = asyncio.run(container.scheduler_service.run_pending_tick(now))

        assert len(first) == 1
        assert second == []
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_jobs_api_create_list_and_run() -> None:
    workspace = _make_test_workspace()
    settings = AppSettings(
        storage_backend="memory",
        workspace_root=workspace,
        skills_root=ROOT / "skills",
    )
    try:
        container = build_container(settings)
        client = TestClient(create_api(settings, container=container))

        create_response = client.post(
            "/jobs",
            json={
                "job_id": "api-job",
                "name": "API Job",
                "cron": "* * * * *",
                "input_prompt": "hello api job",
                "target_channel": "scheduler",
                "skills": ["writing_assistant"],
            },
        )
        assert create_response.status_code == 200

        list_response = client.get("/jobs")
        assert list_response.status_code == 200
        assert list_response.json()[0]["job_id"] == "api-job"
        assert list_response.json()[0]["skills"] == ["writing_assistant"]

        run_response = client.post("/jobs/api-job/run")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "completed"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_jobs_api_returns_404_for_missing_job() -> None:
    settings = AppSettings(storage_backend="memory")
    client = TestClient(create_api(settings, container=build_container(settings)))

    response = client.post("/jobs/missing/run")
    assert response.status_code == 404
    assert response.json()["error_code"] == "job_not_found"


def test_scheduler_api_status_start_stop() -> None:
    settings = AppSettings(storage_backend="memory")
    client = TestClient(create_api(settings, container=build_container(settings)))

    status_response = client.get("/scheduler/status")
    assert status_response.status_code == 200
    assert status_response.json()["running"] is False

    start_response = client.post("/scheduler/start")
    assert start_response.status_code == 200
    assert start_response.json()["running"] is True

    stop_response = client.post("/scheduler/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False
