import os
import shutil
from pathlib import Path

import yaml

from lightclaw.domain.errors import SkillDependencyError, SkillNotFoundError
from lightclaw.domain.skills.base import SkillRegistry
from lightclaw.domain.skills.models import SkillContext, SkillDefinition


class FilesystemSkillRegistry(SkillRegistry):
    def __init__(self, skills_root: Path) -> None:
        self._skills_root = skills_root
        self._skills = self._load_skills()

    async def list_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    async def get_skill(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    async def resolve_context(self, requested_skill_ids: list[str]) -> SkillContext:
        if not requested_skill_ids:
            return SkillContext()

        active_skills: list[SkillDefinition] = []
        seen_tools: set[str] = set()
        for skill_id in requested_skill_ids:
            skill = self._skills.get(skill_id)
            if skill is None:
                raise SkillNotFoundError(f"Skill '{skill_id}' was not found.")
            self._check_dependencies(skill)
            active_skills.append(skill)
            seen_tools.update(skill.tools)

        return SkillContext(
            active_skills=active_skills,
            prompt_fragments=[skill.prompt for skill in active_skills if skill.prompt.strip()],
            tool_names=sorted(seen_tools),
        )

    def _load_skills(self) -> dict[str, SkillDefinition]:
        if not self._skills_root.exists():
            return {}

        loaded: dict[str, SkillDefinition] = {}
        for entry in self._skills_root.iterdir():
            if not entry.is_dir():
                continue
            metadata_path = entry / "skill.yaml"
            if not metadata_path.exists():
                continue
            metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
            prompt_file = metadata.get("prompt_file", "SKILL.md")
            prompt_path = entry / prompt_file
            prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
            dependency_payload = metadata.get("dependencies", {}) or {}
            if not isinstance(dependency_payload, dict):
                dependency_payload = {}
            dependency_payload = {
                "env_vars": list(dependency_payload.get("env_vars") or []),
                "commands": list(dependency_payload.get("commands") or []),
            }
            skill = SkillDefinition(
                skill_id=str(metadata["id"]),
                name=str(metadata.get("name") or metadata["id"]),
                description=str(metadata.get("description") or ""),
                prompt=prompt.strip(),
                tools=[str(tool) for tool in metadata.get("tools", [])],
                dependencies=dependency_payload,
            )
            loaded[skill.skill_id] = skill
        return loaded

    def _check_dependencies(self, skill: SkillDefinition) -> None:
        missing_env_vars = [
            env_var
            for env_var in skill.dependencies.env_vars
            if not os.getenv(env_var)
        ]
        missing_commands = [
            command
            for command in skill.dependencies.commands
            if shutil.which(command) is None
        ]
        if missing_env_vars or missing_commands:
            parts: list[str] = []
            if missing_env_vars:
                parts.append(f"missing env vars: {', '.join(missing_env_vars)}")
            if missing_commands:
                parts.append(f"missing commands: {', '.join(missing_commands)}")
            raise SkillDependencyError(
                f"Skill '{skill.skill_id}' cannot be activated: {'; '.join(parts)}."
            )
