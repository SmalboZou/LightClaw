from lightclaw.domain.skills.base import SkillRegistry
from lightclaw.domain.skills.models import SkillContext, SkillDefinition
from lightclaw.domain.tools.base import FilteredToolRegistry, ToolRegistry


class SkillService:
    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    async def list_skills(self) -> list[SkillDefinition]:
        return await self._registry.list_skills()

    async def resolve_context(self, requested_skill_ids: list[str]) -> SkillContext:
        return await self._registry.resolve_context(requested_skill_ids)

    async def apply_tool_context(
        self,
        base_registry: ToolRegistry,
        skill_context: SkillContext,
    ) -> ToolRegistry:
        if not skill_context.tool_names:
            return base_registry
        return FilteredToolRegistry(base_registry, skill_context.tool_names)
