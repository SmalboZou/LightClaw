import asyncio
from pathlib import Path
import shutil
import uuid

from lightclaw.bootstrap import build_container
from lightclaw.application.services.memory_service import MemoryService
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.domain.errors import PolicyViolationError
from lightclaw.domain.jobs.models import JobDefinition
from lightclaw.domain.memory.models import MemoryWriteRequest


def test_chat_service_returns_reply() -> None:
    container = build_container(AppSettings(storage_backend="memory"))
    response = asyncio.run(
        container.chat_service.chat(
            AgentRequest(
                session_id="test-session",
                user_id="test-user",
                message="hello",
                channel="test",
            )
        )
    )

    assert "hello" in response.reply


def _make_test_workspace() -> Path:
    workspace = Path("tests/.tmp") / str(uuid.uuid4())
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def test_chat_service_executes_tool_call() -> None:
    tmp_path = _make_test_workspace()
    container = build_container(
        AppSettings(workspace_root=tmp_path, tool_policy="workspace_write")
    )

    try:
        response = asyncio.run(
            container.chat_service.chat(
                AgentRequest(
                    session_id="tool-session",
                    user_id="test-user",
                    message="/tool filesystem.write notes/agent.txt hello-agent",
                    channel="test",
                )
            )
        )

        assert response.tool_results[0].name == "filesystem.write"
        assert (tmp_path / "notes" / "agent.txt").read_text(encoding="utf-8") == "hello-agent"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chat_service_rejects_disallowed_tool() -> None:
    tmp_path = _make_test_workspace()
    container = build_container(AppSettings(workspace_root=tmp_path, tool_policy="read_only"))

    try:
        try:
            asyncio.run(
                container.chat_service.chat(
                    AgentRequest(
                        session_id="policy-session",
                        user_id="test-user",
                        message="/tool filesystem.write notes/blocked.txt blocked",
                        channel="test",
                    )
                )
            )
        except PolicyViolationError:
            return
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)

    raise AssertionError("Expected PolicyViolationError to be raised")


def test_sqlite_session_history_persists_across_containers() -> None:
    workspace = _make_test_workspace()
    database_url = f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}"
    settings = AppSettings(
        storage_backend="sqlite",
        database_url=database_url,
        workspace_root=workspace,
    )

    try:
        first_container = build_container(settings)
        first_response = asyncio.run(
            first_container.chat_service.chat(
                AgentRequest(
                    session_id="persisted-session",
                    user_id="persisted-user",
                    message="first",
                    channel="test",
                )
            )
        )
        assert "turns=1" in first_response.reply

        second_container = build_container(settings)
        second_response = asyncio.run(
            second_container.chat_service.chat(
                AgentRequest(
                    session_id="persisted-session",
                    user_id="persisted-user",
                    message="second",
                    channel="test",
                )
            )
        )
        assert "turns=3" in second_response.reply
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_sqlite_memory_persists_across_containers() -> None:
    workspace = _make_test_workspace()
    database_url = f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}"
    settings = AppSettings(
        storage_backend="sqlite",
        database_url=database_url,
        workspace_root=workspace,
    )

    try:
        first_container = build_container(settings)
        asyncio.run(first_container.memory_store.add_memory("memory-user", "remember this"))

        second_container = build_container(settings)
        memories = asyncio.run(second_container.memory_store.get_memories("memory-user"))
        assert memories == ["remember this"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_memory_service_stores_structured_records_and_deduplicates() -> None:
    container = build_container(AppSettings(storage_backend="memory"))
    memory_service = container.memory_service

    first = asyncio.run(
        memory_service.remember(
            MemoryWriteRequest(
                user_id="memory-user",
                content="Prefers concise answers.",
                kind="preference",
                scope="user",
            )
        )
    )
    second = asyncio.run(
        memory_service.remember(
            MemoryWriteRequest(
                user_id="memory-user",
                content="Prefers concise answers.",
                kind="preference",
                scope="user",
            )
        )
    )
    context = asyncio.run(memory_service.build_context("memory-user"))

    assert first is True
    assert second is False
    assert context == ["[preference] Prefers concise answers."]


def test_memory_service_filters_session_scoped_records() -> None:
    container = build_container(AppSettings(storage_backend="memory"))
    memory_service = container.memory_service

    asyncio.run(
        memory_service.remember(
            MemoryWriteRequest(
                user_id="memory-user",
                content="Project codename is LightClaw.",
                kind="project_fact",
                scope="session",
                session_id="session-a",
            )
        )
    )

    session_a = asyncio.run(memory_service.build_context("memory-user", session_id="session-a"))
    session_b = asyncio.run(memory_service.build_context("memory-user", session_id="session-b"))

    assert session_a == ["[project_fact] Project codename is LightClaw."]
    assert session_b == []


def test_chat_service_extracts_memory_after_reply() -> None:
    container = build_container(AppSettings(storage_backend="memory"))

    asyncio.run(
        container.chat_service.chat(
            AgentRequest(
                session_id="extract-session",
                user_id="extract-user",
                message="remember: prefers markdown output",
                channel="test",
            )
        )
    )

    context = asyncio.run(container.memory_service.build_context("extract-user"))
    assert context == ["[project_fact] prefers markdown output"]


def test_chat_service_extracts_session_scoped_memory() -> None:
    container = build_container(AppSettings(storage_backend="memory"))

    asyncio.run(
        container.chat_service.chat(
            AgentRequest(
                session_id="session-memory",
                user_id="extract-user",
                message="session: current sprint is alpha",
                channel="test",
            )
        )
    )

    matching = asyncio.run(
        container.memory_service.build_context("extract-user", session_id="session-memory")
    )
    non_matching = asyncio.run(
        container.memory_service.build_context("extract-user", session_id="other-session")
    )

    assert matching == ["[project_fact] current sprint is alpha"]
    assert non_matching == []


def test_chat_service_extraction_deduplicates_on_repeat_messages() -> None:
    container = build_container(AppSettings(storage_backend="memory"))

    for _ in range(2):
        asyncio.run(
            container.chat_service.chat(
                AgentRequest(
                    session_id="dedupe-session",
                    user_id="dedupe-user",
                    message="preference: wants short bullet points",
                    channel="test",
                )
            )
        )

    context = asyncio.run(container.memory_service.build_context("dedupe-user"))
    assert context == ["[preference] wants short bullet points"]


def test_sqlite_execution_logs_persist() -> None:
    workspace = _make_test_workspace()
    database_url = f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}"
    settings = AppSettings(
        storage_backend="sqlite",
        database_url=database_url,
        workspace_root=workspace,
    )

    try:
        container = build_container(settings)
        asyncio.run(
            container.chat_service.chat(
                AgentRequest(
                    session_id="log-session",
                    user_id="log-user",
                    message="/tool echo.text persisted-log",
                    channel="test",
                )
            )
        )
        second_container = build_container(settings)
        events = asyncio.run(second_container.execution_log_store.list_events("log-session"))
        event_types = [event["event_type"] for event in events]
        assert "agent_run_started" in event_types
        assert "tool_execution_started" in event_types
        assert "agent_run_completed" in event_types
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_sqlite_structured_memory_persists_across_containers() -> None:
    workspace = _make_test_workspace()
    database_url = f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}"
    settings = AppSettings(
        storage_backend="sqlite",
        database_url=database_url,
        workspace_root=workspace,
    )

    try:
        first_container = build_container(settings)
        asyncio.run(
            first_container.memory_service.remember(
                MemoryWriteRequest(
                    user_id="structured-user",
                    content="Runs daily summary at 9am.",
                    kind="task_rule",
                    scope="user",
                )
            )
        )

        second_container = build_container(settings)
        context = asyncio.run(second_container.memory_service.build_context("structured-user"))
        assert context == ["[task_rule] Runs daily summary at 9am."]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_sqlite_job_store_persists() -> None:
    workspace = _make_test_workspace()
    database_url = f"sqlite:///{(workspace / 'lightclaw.db').as_posix()}"
    settings = AppSettings(
        storage_backend="sqlite",
        database_url=database_url,
        workspace_root=workspace,
    )

    try:
        first_container = build_container(settings)
        asyncio.run(
            first_container.job_store.upsert_job(
                JobDefinition(
                    job_id="daily-brief",
                    name="Daily Brief",
                    cron="0 9 * * *",
                    input_prompt="Summarize project status.",
                    target_channel="telegram",
                    last_status="ready",
                )
            )
        )

        second_container = build_container(settings)
        job = asyncio.run(second_container.job_store.get_job("daily-brief"))
        assert job is not None
        assert job.name == "Daily Brief"
        assert job.last_status == "ready"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
