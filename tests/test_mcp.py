import asyncio
import json
from pathlib import Path
import shutil
import uuid

import pytest

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.domain.errors import PolicyViolationError
from lightclaw.infrastructure.mcp.filesystem_client import FilesystemMCPClient
from lightclaw.infrastructure.mcp.tool_registry import MCPToolRegistry


def test_mcp_tool_registry_loads_manifest_tools() -> None:
    workspace = _make_test_root()
    try:
        servers_root = workspace / "servers"
        _write_server_manifest(servers_root)
        registry = MCPToolRegistry(FilesystemMCPClient(servers_root))

        names = asyncio.run(registry.list_tool_names())

        assert "mcp.demo.echo" in names
        assert "mcp.demo.netprobe" in names
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_chat_service_executes_mcp_tool() -> None:
    workspace = _make_test_root()
    try:
        servers_root = workspace / "servers"
        _write_server_manifest(servers_root)
        container = build_container(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                mcp_servers_root=servers_root,
            )
        )

        response = asyncio.run(
            container.chat_service.chat(
                AgentRequest(
                    session_id="mcp-session",
                    user_id="mcp-user",
                    message="/tool mcp.demo.echo hello-mcp",
                    channel="test",
                )
            )
        )

        assert response.tool_results[0].name == "mcp.demo.echo"
        assert response.tool_results[0].output == "mcp-echo:hello-mcp"
        assert "mcp-echo:hello-mcp" in response.reply
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_mcp_tool_respects_policy_scope() -> None:
    workspace = _make_test_root()
    try:
        servers_root = workspace / "servers"
        _write_server_manifest(servers_root)
        container = build_container(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                mcp_servers_root=servers_root,
                allow_network_access=False,
            )
        )

        with pytest.raises(PolicyViolationError):
            asyncio.run(
                container.chat_service.chat(
                    AgentRequest(
                        session_id="mcp-denied",
                        user_id="mcp-user",
                        message="/tool mcp.demo.netprobe blocked",
                        channel="test",
                    )
                )
            )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _write_server_manifest(servers_root: Path) -> None:
    servers_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "server_id": "demo",
        "tools": [
            {
                "name": "echo",
                "description": "Echo through MCP.",
                "required_scope": "read_only",
                "argument_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
                "response_template": "mcp-echo:{text}",
            },
            {
                "name": "netprobe",
                "description": "Network-classified MCP tool.",
                "required_scope": "network_access",
                "argument_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
                "response_template": "network-probe:{text}",
            },
        ],
    }
    (servers_root / "demo.json").write_text(json.dumps(payload), encoding="utf-8")


def _make_test_root() -> Path:
    root = Path("tests/.tmp") / str(uuid.uuid4())
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()
