from lightclaw.domain.agent.models import ToolResult
from lightclaw.domain.mcp.base import MCPClient
from lightclaw.domain.mcp.models import MCPToolSpec
from lightclaw.domain.tools.base import Tool, ToolRegistry
from lightclaw.domain.tools.models import ToolExecutionContext


class MCPTool(Tool):
    def __init__(self, client: MCPClient, spec: MCPToolSpec) -> None:
        self._client = client
        self._spec = spec
        self.name = spec.exposed_name
        self.description = spec.description
        self.required_scope = spec.required_scope
        self.timeout_seconds = spec.timeout_seconds
        self.argument_schema = spec.argument_schema
        self.audit_enabled = True

    async def run(self, arguments: dict[str, object], context: ToolExecutionContext) -> ToolResult:
        result = await self._client.call_tool(
            server_id=self._spec.server_id,
            tool_name=self._spec.name,
            arguments=arguments,
        )
        return ToolResult(name=self.name, output=result.content)


class MCPToolRegistry(ToolRegistry):
    def __init__(self, client: MCPClient) -> None:
        self._client = client

    async def list_tool_names(self) -> list[str]:
        tools = await self.list_tools()
        return [tool.name for tool in tools]

    async def list_tools(self) -> list[Tool]:
        specs = await self._client.list_tools()
        return [MCPTool(self._client, spec) for spec in specs]

    async def get_tool(self, name: str) -> Tool | None:
        specs = await self._client.list_tools()
        for spec in specs:
            if spec.exposed_name == name:
                return MCPTool(self._client, spec)
        return None
