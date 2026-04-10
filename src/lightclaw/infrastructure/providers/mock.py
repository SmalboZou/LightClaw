from lightclaw.domain.agent.models import AgentTurn, ToolCall
from lightclaw.domain.providers.base import ModelProvider
from lightclaw.domain.providers.models import (
    MemoryExtractionCandidate,
    ProviderProfile,
    ProviderResponse,
)
from lightclaw.domain.tools.base import ToolRegistry


class MockProvider(ModelProvider):
    """Deterministic provider used to exercise the first real agent loop."""

    def profile(self) -> ProviderProfile:
        return ProviderProfile(
            backend="mock",
            model="mock",
            supports_tools=True,
            supports_streaming=False,
            supports_usage_reporting=False,
        )

    async def generate_next(
        self,
        message: str,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
        tool_registry: ToolRegistry,
    ) -> ProviderResponse:
        if history and history[-1].role == "tool":
            tool_turn = history[-1]
            return ProviderResponse(
                final_text=f"Tool {tool_turn.name} returned: {tool_turn.content}"
            )

        if message.startswith("/tool "):
            return ProviderResponse(tool_calls=[self._parse_tool_call(message)])

        tool_names = await tool_registry.list_tool_names()
        memory_hint = f" | memories={len(memories)}" if memories else ""
        history_hint = f" | turns={len(history)}"
        instruction_hint = f" | instructions={len(instructions)}" if instructions else ""
        return ProviderResponse(
            final_text=(
                f"[mock-provider] received: {message}"
                f"{history_hint}{memory_hint}"
                f"{instruction_hint}"
                f" | tools={', '.join(tool_names) if tool_names else 'none'}"
            )
        )

    def _parse_tool_call(self, message: str) -> ToolCall:
        import shlex

        raw = message.removeprefix("/tool ").strip()
        if not raw:
            return ToolCall(name="echo.text", arguments={"text": ""})

        tool_name, _, remainder = raw.partition(" ")
        remainder = remainder.strip()

        if tool_name == "echo.text":
            return ToolCall(name=tool_name, arguments={"text": remainder})
        if tool_name == "session.count_turns":
            return ToolCall(name=tool_name, arguments={})
        if tool_name == "filesystem.read":
            path = remainder or "notes/default.txt"
            return ToolCall(name=tool_name, arguments={"path": path})
        if tool_name == "filesystem.write":
            path, _, content = remainder.partition(" ")
            path = path or "notes/default.txt"
            return ToolCall(name=tool_name, arguments={"path": path, "content": content})
        if tool_name == "shell.exec":
            command = shlex.split(remainder, posix=False) if remainder else []
            return ToolCall(name=tool_name, arguments={"command": command})
        if tool_name == "http.fetch":
            url = remainder or "https://example.com"
            return ToolCall(name=tool_name, arguments={"url": url})
        if tool_name == "browser.open":
            parts = shlex.split(remainder, posix=False) if remainder else []
            session_name = parts[0] if parts else "browser-session"
            start_url = parts[1] if len(parts) > 1 else None
            payload = {"session_name": session_name}
            if start_url:
                payload["start_url"] = start_url
            return ToolCall(name=tool_name, arguments=payload)
        if tool_name == "browser.navigate":
            parts = shlex.split(remainder, posix=False) if remainder else []
            return ToolCall(
                name=tool_name,
                arguments={
                    "session_id": parts[0] if parts else "missing-session",
                    "url": parts[1] if len(parts) > 1 else "https://example.com",
                },
            )
        if tool_name in {"browser.snapshot", "browser.close"}:
            return ToolCall(
                name=tool_name,
                arguments={"session_id": remainder or "missing-session"},
            )
        if tool_name == "weather.lookup_web":
            return ToolCall(name=tool_name, arguments={"location": remainder or "beijing"})

        return ToolCall(
            name=tool_name,
            arguments={"text": remainder} if remainder else {},
        )

    async def extract_memories(
        self,
        user_message: str,
        assistant_reply: str,
    ) -> list[MemoryExtractionCandidate]:
        text = user_message.strip()
        lowered = text.lower()
        if lowered.startswith("remember:"):
            return [
                MemoryExtractionCandidate(
                    content=text.split(":", 1)[1].strip(),
                    kind="project_fact",
                    scope="user",
                )
            ]
        if lowered.startswith("preference:"):
            return [
                MemoryExtractionCandidate(
                    content=text.split(":", 1)[1].strip(),
                    kind="preference",
                    scope="user",
                )
            ]
        if lowered.startswith("task:"):
            return [
                MemoryExtractionCandidate(
                    content=text.split(":", 1)[1].strip(),
                    kind="task_rule",
                    scope="user",
                )
            ]
        if lowered.startswith("session:"):
            return [
                MemoryExtractionCandidate(
                    content=text.split(":", 1)[1].strip(),
                    kind="project_fact",
                    scope="session",
                )
            ]
        return []
