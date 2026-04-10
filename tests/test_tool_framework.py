import asyncio
import sys
from pathlib import Path
import shutil
import uuid

import httpx
import pytest

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.domain.errors import PolicyViolationError
from lightclaw.infrastructure.tools.registry import (
    FilesystemReadTool,
    HttpFetchTool,
    InMemoryToolRegistry,
    ShellExecTool,
)


def test_tool_registry_exposes_schema_definitions() -> None:
    registry = InMemoryToolRegistry()
    tools = asyncio.run(registry.list_tools())
    definitions = [tool.definition() for tool in tools]
    names = [definition.name for definition in definitions]

    assert "filesystem.read" in names
    assert "shell.exec" in names
    assert any(definition.argument_schema for definition in definitions)


def _make_test_workspace() -> Path:
    workspace = Path("tests/.tmp") / str(uuid.uuid4())
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def test_filesystem_read_tool_reads_workspace_file() -> None:
    tmp_path = _make_test_workspace()
    target = tmp_path / "docs" / "note.txt"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("hello file", encoding="utf-8")
        tool = FilesystemReadTool()

        result = asyncio.run(
            tool.run(
                {"path": "docs/note.txt"},
                context=_tool_context(tmp_path),
            )
        )

        assert result.output == "hello file"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_shell_exec_tool_runs_allowed_command() -> None:
    tmp_path = _make_test_workspace()
    async def fake_runner(command: list[str], context: object) -> tuple[int, str, str]:
        return 0, f"ran:{' '.join(command)}", ""

    try:
        response = asyncio.run(
            ShellExecTool(runner=fake_runner).run(
                {"command": [sys.executable, "-c", "print('hi-shell')"]},
                _tool_context(
                    tmp_path,
                    allow_process_exec=True,
                    allowed_commands=[sys.executable],
                ),
            )
        )

        assert response.name == "shell.exec"
        assert "hi-shell" in response.output
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_shell_exec_tool_rejects_disallowed_command() -> None:
    tmp_path = _make_test_workspace()
    container = build_container(
        AppSettings(
            storage_backend="memory",
            workspace_root=tmp_path,
            allow_process_exec=True,
            allowed_commands=["allowed-only"],
            provider_backend="mock",
        )
    )

    try:
        try:
            asyncio.run(
                container.chat_service.chat(
                    AgentRequest(
                        session_id="shell-denied",
                        user_id="shell-user",
                        message=f"/tool shell.exec {sys.executable} -c print('nope')",
                        channel="test",
                    )
                )
            )
        except PolicyViolationError:
            return
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)

    raise AssertionError("Expected PolicyViolationError")


def test_http_fetch_tool_reads_content_with_network_access() -> None:
    tmp_path = _make_test_workspace()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="network content")

        tool = HttpFetchTool(
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="https://example.test",
            )
        )
        result = await tool.run(
            {"url": "https://example.test/page"},
            context=_tool_context(tmp_path, allow_network_access=True),
        )
        assert result.output == "network content"

    try:
        asyncio.run(_run())
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chat_service_validates_tool_arguments_before_execution() -> None:
    workspace = _make_test_workspace()
    container = build_container(
        AppSettings(
            storage_backend="memory",
            workspace_root=workspace,
            allow_process_exec=True,
            provider_backend="mock",
        )
    )

    try:
        from lightclaw.domain.errors import ToolArgumentValidationError

        with pytest.raises(ToolArgumentValidationError):
            asyncio.run(
                container.chat_service.chat(
                    AgentRequest(
                        session_id="shell-invalid",
                        user_id="shell-user",
                        message="/tool shell.exec",
                        channel="test",
                    )
                )
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_chat_service_shapes_large_and_sensitive_tool_output() -> None:
    workspace = _make_test_workspace()
    target = workspace / "docs" / "secret.txt"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "Authorization: Bearer super-secret-token\n"
            + ("A" * 2500)
            + "\nX-API-Key: hidden-value",
            encoding="utf-8",
        )
        container = build_container(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                provider_backend="mock",
            )
        )

        response = asyncio.run(
            container.chat_service.chat(
                AgentRequest(
                    session_id="read-secret",
                    user_id="tool-user",
                    message="/tool filesystem.read docs/secret.txt",
                    channel="test",
                )
            )
        )

        output = response.tool_results[0].output
        assert "[REDACTED]" in output
        assert "super-secret-token" not in output
        assert "hidden-value" not in output
        assert output.endswith("...[truncated]")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _tool_context(
    workspace_root: Path,
    *,
    allow_process_exec: bool = False,
    allow_network_access: bool = False,
    allowed_commands: list[str] | None = None,
) -> object:
    from lightclaw.domain.tools.models import ToolExecutionContext

    return ToolExecutionContext(
        session_id="tool-session",
        user_id="tool-user",
        workspace_root=workspace_root.resolve(),
        allow_process_exec=allow_process_exec,
        allow_network_access=allow_network_access,
        allowed_commands=allowed_commands or [],
        history=[],
    )
