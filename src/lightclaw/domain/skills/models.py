from pydantic import BaseModel, Field


class SkillDependencySpec(BaseModel):
    env_vars: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    skill_id: str
    name: str
    description: str
    prompt: str
    tools: list[str] = Field(default_factory=list)
    dependencies: SkillDependencySpec = Field(default_factory=SkillDependencySpec)


class SkillContext(BaseModel):
    active_skills: list[SkillDefinition] = Field(default_factory=list)
    prompt_fragments: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
