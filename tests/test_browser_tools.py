import asyncio
import json
import shutil
import uuid
from pathlib import Path

import pytest

from lightclaw.domain.errors import PolicyViolationError
from lightclaw.domain.tools.models import ToolExecutionContext
from lightclaw.infrastructure.browser.service import build_browser_service
from lightclaw.infrastructure.tools.browser_tools import BrowserTypeTool
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry


def _make_test_workspace() -> Path:
    workspace = Path("tests/.tmp") / str(uuid.uuid4())
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def _tool_context(
    workspace_root: Path,
    *,
    browser_enabled: bool = True,
    browser_allowed_domains: list[str] | None = None,
    browser_allow_persistent_auth: bool = False,
) -> ToolExecutionContext:
    return ToolExecutionContext(
        session_id="browser-session",
        user_id="browser-user",
        workspace_root=workspace_root,
        allow_process_exec=False,
        allow_network_access=False,
        allowed_commands=[],
        history=[],
        browser_enabled=browser_enabled,
        browser_backend="mock",
        browser_headless=True,
        browser_allowed_domains=browser_allowed_domains or [],
        browser_allow_persistent_auth=browser_allow_persistent_auth,
        browser_profile_root=(workspace_root / ".lightclaw" / "browser").resolve(),
        mail_web_provider="gmail",
        weather_url_template="https://wttr.in/{location}",
    )


def test_browser_tools_are_registered() -> None:
    registry = InMemoryToolRegistry(browser_service=build_browser_service("mock"))

    tools = asyncio.run(registry.list_tools())
    names = [tool.name for tool in tools]

    assert "browser.open" in names
    assert "browser.navigate" in names
    assert "weather.lookup_web" in names
    assert "mail.send_web" in names


def test_browser_open_and_snapshot_work_with_mock_service() -> None:
    workspace = _make_test_workspace()
    registry = InMemoryToolRegistry(browser_service=build_browser_service("mock"))
    context = _tool_context(workspace, browser_allowed_domains=["example.com"])
    try:
        open_tool = asyncio.run(registry.get_tool("browser.open"))
        snapshot_tool = asyncio.run(registry.get_tool("browser.snapshot"))

        opened = asyncio.run(
            open_tool.run(
                {
                    "session_name": "demo",
                    "start_url": "https://example.com/weather",
                },
                context,
            )
        )
        session_id = json.loads(opened.output)["session_id"]
        snapshot = asyncio.run(snapshot_tool.run({"session_id": session_id}, context))
        payload = json.loads(snapshot.output)

        assert payload["url"] == "https://example.com/weather"
        assert payload["title"] == "example.com"
        assert "Loaded https://example.com/weather" in payload["visible_text"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_browser_navigation_denied_when_domain_not_allowed() -> None:
    workspace = _make_test_workspace()
    registry = InMemoryToolRegistry(browser_service=build_browser_service("mock"))
    context = _tool_context(workspace, browser_allowed_domains=["wttr.in"])
    try:
        open_tool = asyncio.run(registry.get_tool("browser.open"))
        with pytest.raises(PolicyViolationError):
            asyncio.run(
                open_tool.run(
                    {
                        "session_name": "blocked",
                        "start_url": "https://mail.google.com/mail/u/0/#inbox",
                    },
                    context,
                )
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_browser_tools_fail_when_browser_disabled() -> None:
    workspace = _make_test_workspace()
    registry = InMemoryToolRegistry(browser_service=build_browser_service("mock"))
    context = _tool_context(workspace, browser_enabled=False)
    try:
        open_tool = asyncio.run(registry.get_tool("browser.open"))
        with pytest.raises(PolicyViolationError):
            asyncio.run(open_tool.run({"session_name": "disabled"}, context))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_weather_lookup_web_returns_mock_weather_summary() -> None:
    workspace = _make_test_workspace()
    registry = InMemoryToolRegistry(browser_service=build_browser_service("mock"))
    context = _tool_context(workspace, browser_allowed_domains=["wttr.in"])
    try:
        weather_tool = asyncio.run(registry.get_tool("weather.lookup_web"))
        result = asyncio.run(weather_tool.run({"location": "beijing"}, context))
        payload = json.loads(result.output)

        assert payload["location"] == "beijing"
        assert payload["url"] == "https://wttr.in/beijing"
        assert "Weather for beijing" in payload["summary"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_mail_send_web_uses_mock_gmail_flow() -> None:
    workspace = _make_test_workspace()
    registry = InMemoryToolRegistry(browser_service=build_browser_service("mock"))
    context = _tool_context(
        workspace,
        browser_allowed_domains=["mail.google.com"],
        browser_allow_persistent_auth=True,
    )
    try:
        mail_tool = asyncio.run(registry.get_tool("mail.send_web"))
        result = asyncio.run(
            mail_tool.run(
                {
                    "to": "dev@example.com",
                    "subject": "Status",
                    "body": "Nightly job completed.",
                },
                context,
            )
        )
        payload = json.loads(result.output)

        assert payload["provider"] == "gmail"
        assert payload["status"] == "sent"
        assert payload["to"] == "dev@example.com"
        assert payload["subject"] == "Status"
        assert payload["title"] == "Message sent"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_browser_type_redacts_secret_input() -> None:
    workspace = _make_test_workspace()
    browser_service = build_browser_service("mock")
    registry = InMemoryToolRegistry(browser_service=browser_service)
    context = _tool_context(workspace, browser_allowed_domains=["mail.google.com"])
    try:
        open_tool = asyncio.run(registry.get_tool("browser.open"))
        open_result = asyncio.run(
            open_tool.run(
                {
                    "session_name": "compose",
                    "start_url": "https://mail.google.com/mail/u/0/#inbox?compose=new",
                },
                context,
            )
        )
        session_id = json.loads(open_result.output)["session_id"]
        tool = BrowserTypeTool(browser_service)
        result = asyncio.run(
            tool.run(
                {
                    "session_id": session_id,
                    "selector": "input[aria-label='Recipients']",
                    "text": "hidden@example.com",
                    "secret": True,
                },
                context,
            )
        )
        payload = json.loads(result.output)

        assert payload["secret"] is True
        assert payload["text"] == "[REDACTED]"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
