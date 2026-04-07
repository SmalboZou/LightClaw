from pydantic import BaseModel, Field, model_validator

from lightclaw.domain.agent.models import ToolCall


class ProviderConfig(BaseModel):
    backend: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None

    @model_validator(mode="after")
    def validate_for_backend(self) -> "ProviderConfig":
        if self.backend in {"openai_compatible", "anthropic"}:
            if not self.model:
                raise ValueError(f"Provider backend '{self.backend}' requires a model.")
            if not self.base_url:
                raise ValueError(f"Provider backend '{self.backend}' requires a base_url.")
        return self


class ProviderProfile(BaseModel):
    backend: str
    model: str | None = None
    supports_tools: bool = True
    supports_streaming: bool = False
    supports_usage_reporting: bool = True


class ProviderStreamEvent(BaseModel):
    event_type: str
    text: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    final_text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


class MemoryExtractionCandidate(BaseModel):
    content: str
    kind: str = "project_fact"
    scope: str = "user"
