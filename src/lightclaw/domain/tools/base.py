from abc import ABC, abstractmethod
from typing import Any

from lightclaw.domain.agent.models import ToolResult
from lightclaw.domain.tools.models import ToolDefinition, ToolExecutionContext, ToolScope


class Tool(ABC):
    name: str
    description: str
    required_scope: ToolScope = "read_only"
    timeout_seconds: float = 5.0
    argument_schema: dict[str, Any] = {}
    audit_enabled: bool = True

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            required_scope=self.required_scope,
            timeout_seconds=self.timeout_seconds,
            argument_schema=self.argument_schema,
            audit_enabled=self.audit_enabled,
        )

    @abstractmethod
    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        raise NotImplementedError

class ToolRegistry(ABC):
    @abstractmethod
    async def list_tool_names(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def list_tools(self) -> list[Tool]:
        raise NotImplementedError

    @abstractmethod
    async def get_tool(self, name: str) -> Tool | None:
        raise NotImplementedError


class FilteredToolRegistry(ToolRegistry):
    def __init__(self, base_registry: ToolRegistry, allowed_tool_names: list[str]) -> None:
        self._base_registry = base_registry
        self._allowed_tool_names = set(allowed_tool_names)

    async def list_tool_names(self) -> list[str]:
        names = await self._base_registry.list_tool_names()
        return [name for name in names if name in self._allowed_tool_names]

    async def list_tools(self) -> list[Tool]:
        tools = await self._base_registry.list_tools()
        return [tool for tool in tools if tool.name in self._allowed_tool_names]

    async def get_tool(self, name: str) -> Tool | None:
        if name not in self._allowed_tool_names:
            return None
        return await self._base_registry.get_tool(name)


class CompositeToolRegistry(ToolRegistry):
    def __init__(self, registries: list[ToolRegistry]) -> None:
        self._registries = registries

    async def list_tool_names(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for registry in self._registries:
            for name in await registry.list_tool_names():
                if name in seen:
                    continue
                seen.add(name)
                names.append(name)
        return names

    async def list_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        seen: set[str] = set()
        for registry in self._registries:
            for tool in await registry.list_tools():
                if tool.name in seen:
                    continue
                seen.add(tool.name)
                tools.append(tool)
        return tools

    async def get_tool(self, name: str) -> Tool | None:
        for registry in self._registries:
            tool = await registry.get_tool(name)
            if tool is not None:
                return tool
        return None
