import asyncio
from pathlib import Path
from typing import Any

import httpx

from lightclaw.domain.agent.models import ToolResult
from lightclaw.domain.errors import PolicyViolationError
from lightclaw.domain.tools.base import Tool, ToolRegistry
from lightclaw.domain.tools.models import ToolExecutionContext


def _resolve_workspace_path(workspace_root: Path, raw_path: str) -> Path:
    target = (workspace_root / raw_path).resolve()
    root = workspace_root.resolve()
    if root not in target.parents and target != root:
        raise ValueError("Target path escapes the configured workspace root.")
    return target


class EchoTool(Tool):
    name = "echo.text"
    description = "Return the input text."
    required_scope = "read_only"
    argument_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        return ToolResult(name=self.name, output=str(arguments.get("text", "")))


class SessionCountTurnsTool(Tool):
    name = "session.count_turns"
    description = "Count turns in the current session context."
    required_scope = "read_only"
    argument_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        return ToolResult(name=self.name, output=str(len(context.history)))


class FilesystemReadTool(Tool):
    name = "filesystem.read"
    description = "Read a UTF-8 text file under the configured workspace root."
    required_scope = "read_only"
    argument_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        target = _resolve_workspace_path(context.workspace_root, str(arguments["path"]))
        return ToolResult(name=self.name, output=target.read_text(encoding="utf-8"))


class FilesystemWriteTool(Tool):
    name = "filesystem.write"
    description = "Write UTF-8 text to a file under the configured workspace root."
    required_scope = "workspace_write"
    argument_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        target = _resolve_workspace_path(context.workspace_root, str(arguments["path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(arguments["content"]), encoding="utf-8")
        relative = target.relative_to(context.workspace_root.resolve())
        return ToolResult(name=self.name, output=f"wrote:{relative.as_posix()}")


class ShellExecTool(Tool):
    name = "shell.exec"
    description = "Execute an allowed command without shell expansion."
    required_scope = "process_exec"
    timeout_seconds = 10.0
    argument_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def __init__(self, runner: Any | None = None) -> None:
        self._runner = runner or self._default_runner

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        command = arguments.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError("command must be a non-empty list of strings.")
        executable = command[0]
        if not context.allow_process_exec or (
            context.allowed_commands and executable not in context.allowed_commands
        ):
            raise PolicyViolationError(f"Command '{executable}' is not allowed by policy.")

        exit_code, output, error = await self._runner(command, context)
        result = f"exit_code={exit_code}"
        if output:
            result += f"\nstdout:\n{output}"
        if error:
            result += f"\nstderr:\n{error}"
        return ToolResult(name=self.name, output=result)

    async def _default_runner(
        self,
        command: list[str],
        context: ToolExecutionContext,
    ) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(context.workspace_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            int(process.returncode or 0),
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )


class HttpFetchTool(Tool):
    name = "http.fetch"
    description = "Fetch plain text content from an HTTP or HTTPS URL."
    required_scope = "network_access"
    timeout_seconds = 10.0
    argument_schema = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
        "additionalProperties": False,
    }

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client or httpx.AsyncClient(timeout=self.timeout_seconds)
        self._owns_client = http_client is None

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        if not context.allow_network_access:
            raise PolicyViolationError("Network access is disabled by policy.")
        url = str(arguments["url"])
        response = await self._http_client.get(url, follow_redirects=True)
        response.raise_for_status()
        text = response.text
        if len(text) > 4000:
            text = text[:4000]
        return ToolResult(name=self.name, output=text)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()


class InMemoryToolRegistry(ToolRegistry):
    def __init__(self, tools: list[Tool] | None = None) -> None:
        resolved_tools = tools or [
            EchoTool(),
            SessionCountTurnsTool(),
            FilesystemReadTool(),
            FilesystemWriteTool(),
            ShellExecTool(),
            HttpFetchTool(),
        ]
        self._tools = {tool.name: tool for tool in resolved_tools}

    async def list_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    async def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    async def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)
