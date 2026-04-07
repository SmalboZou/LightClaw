from abc import ABC, abstractmethod

from lightclaw.domain.skills.models import SkillContext, SkillDefinition


class SkillRegistry(ABC):
    @abstractmethod
    async def list_skills(self) -> list[SkillDefinition]:
        raise NotImplementedError

    @abstractmethod
    async def get_skill(self, skill_id: str) -> SkillDefinition | None:
        raise NotImplementedError

    @abstractmethod
    async def resolve_context(self, requested_skill_ids: list[str]) -> SkillContext:
        raise NotImplementedError
