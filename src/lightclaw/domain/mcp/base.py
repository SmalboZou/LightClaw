from abc import ABC, abstractmethod

from lightclaw.domain.mcp.models import MCPCallResult, MCPToolSpec


class MCPClient(ABC):
    @abstractmethod
    async def list_tools(self) -> list[MCPToolSpec]:
        raise NotImplementedError

    @abstractmethod
    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> MCPCallResult:
        raise NotImplementedError
