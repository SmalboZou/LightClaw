import asyncio
from pathlib import Path
import shutil
import uuid

import pytest
from fastapi.testclient import TestClient

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.domain.errors import SkillDependencyError, ToolNotFoundError
from lightclaw.infrastructure.skills.filesystem_registry import FilesystemSkillRegistry
from lightclaw.interfaces.api.app import create_api


def test_filesystem_skill_registry_loads_markdown_and_yaml() -> None:
    tmp_path = _make_test_root()
    _write_skill(
        tmp_path,
        skill_id="writer",
        prompt="Focus on concise writing.",
        tools=["echo.text"],
    )
    try:
        registry = FilesystemSkillRegistry(tmp_path)
        skills = asyncio.run(registry.list_skills())

        assert len(skills) == 1
        assert skills[0].skill_id == "writer"
        assert skills[0].tools == ["echo.text"]
        assert "concise writing" in skills[0].prompt
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_skill_registry_checks_dependencies() -> None:
    tmp_path = _make_test_root()
    _write_skill(
        tmp_path,
        skill_id="requires-env",
        prompt="Requires an env var.",
        tools=["echo.text"],
        env_vars=["LIGHTCLAW_MISSING_ENV"],
    )
    try:
        registry = FilesystemSkillRegistry(tmp_path)
        with pytest.raises(SkillDependencyError):
            asyncio.run(registry.resolve_context(["requires-env"]))
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chat_service_applies_skill_prompts_and_tool_filtering() -> None:
    tmp_path = _make_test_root()
    _write_skill(
        tmp_path,
        skill_id="writer",
        prompt="Always write concise prose.",
        tools=["echo.text"],
    )
    container = build_container(
        AppSettings(
            storage_backend="memory",
            skills_root=tmp_path,
        )
    )
    try:
        response = asyncio.run(
            container.chat_service.chat(
                AgentRequest(
                    session_id="skill-session",
                    user_id="skill-user",
                    message="hello",
                    channel="test",
                    skills=["writer"],
                )
            )
        )

        assert "instructions=1" in response.reply
        assert "tools=echo.text" in response.reply
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chat_service_rejects_tool_outside_active_skill() -> None:
    tmp_path = _make_test_root()
    _write_skill(
        tmp_path,
        skill_id="writer",
        prompt="Only use echo.",
        tools=["echo.text"],
    )
    container = build_container(
        AppSettings(
            storage_backend="memory",
            workspace_root=tmp_path,
            skills_root=tmp_path,
            tool_policy="workspace_write",
        )
    )
    try:
        with pytest.raises(ToolNotFoundError):
            asyncio.run(
                container.chat_service.chat(
                    AgentRequest(
                        session_id="skill-tool-denied",
                        user_id="skill-user",
                        message="/tool filesystem.write notes/out.txt blocked",
                        channel="test",
                        skills=["writer"],
                    )
                )
            )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chat_endpoint_lists_skills_and_accepts_skill_selection() -> None:
    tmp_path = _make_test_root()
    _write_skill(
        tmp_path,
        skill_id="writer",
        prompt="Always write concise prose.",
        tools=["echo.text"],
    )
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                skills_root=tmp_path,
            )
        )
    )
    try:
        skills_response = client.get("/skills")
        chat_response = client.post(
            "/chat",
            json={
                "session_id": "api-skill",
                "user_id": "api-user",
                "message": "hello",
                "channel": "api",
                "skills": ["writer"],
            },
        )

        assert skills_response.status_code == 200
        assert skills_response.json()[0]["skill_id"] == "writer"
        assert chat_response.status_code == 200
        assert "instructions=1" in chat_response.json()["reply"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chat_endpoint_maps_missing_skill_to_404() -> None:
    tmp_path = _make_test_root()
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                skills_root=tmp_path,
            )
        )
    )
    try:
        response = client.post(
            "/chat",
            json={
                "session_id": "missing-skill",
                "user_id": "api-user",
                "message": "hello",
                "channel": "api",
                "skills": ["does-not-exist"],
            },
        )

        assert response.status_code == 404
        assert response.json()["error_code"] == "skill_not_found"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def _write_skill(
    root: Path,
    *,
    skill_id: str,
    prompt: str,
    tools: list[str],
    env_vars: list[str] | None = None,
) -> None:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill.yaml").write_text(
        "\n".join(
            [
                f"id: {skill_id}",
                f"name: {skill_id}",
                "description: test skill",
                "tools:",
                *[f"  - {tool}" for tool in tools],
                "dependencies:",
                "  env_vars:",
                *[f"    - {env_var}" for env_var in (env_vars or [])],
                "  commands: []",
            ]
        ),
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(prompt, encoding="utf-8")


def _make_test_root() -> Path:
    root = Path("tests/.tmp") / str(uuid.uuid4())
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()
