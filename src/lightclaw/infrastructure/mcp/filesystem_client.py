import json
from pathlib import Path

from lightclaw.domain.mcp.base import MCPClient
from lightclaw.domain.mcp.models import MCPCallResult, MCPToolSpec


class FilesystemMCPClient(MCPClient):
    def __init__(self, servers_root: Path) -> None:
        self._servers_root = servers_root
        self._tools = self._load_tools()

    async def list_tools(self) -> list[MCPToolSpec]:
        return list(self._tools.values())

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> MCPCallResult:
        key = f"{server_id}:{tool_name}"
        spec = self._tools[key]
        if spec.response_template:
            return MCPCallResult(content=spec.response_template.format(**arguments))
        return MCPCallResult(content=spec.static_output or "")

    def _load_tools(self) -> dict[str, MCPToolSpec]:
        if not self._servers_root.exists():
            return {}

        loaded: dict[str, MCPToolSpec] = {}
        for path in sorted(self._servers_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            server_id = str(payload["server_id"])
            for raw_tool in payload.get("tools", []):
                spec = MCPToolSpec(
                    server_id=server_id,
                    name=str(raw_tool["name"]),
                    description=str(raw_tool.get("description") or ""),
                    required_scope=raw_tool.get("required_scope", "read_only"),
                    timeout_seconds=float(raw_tool.get("timeout_seconds", 10.0)),
                    argument_schema=raw_tool.get("argument_schema", {}) or {},
                    response_template=raw_tool.get("response_template"),
                    static_output=raw_tool.get("static_output"),
                )
                loaded[f"{server_id}:{spec.name}"] = spec
        return loaded
