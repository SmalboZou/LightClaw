from pathlib import Path

from fastapi.testclient import TestClient

from lightclaw.config.settings import AppSettings
from lightclaw.interfaces.api.app import create_api


def test_health_endpoint() -> None:
    client = TestClient(create_api(AppSettings(storage_backend="memory")))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_endpoint_returns_structured_response() -> None:
    client = TestClient(create_api(AppSettings(storage_backend="memory")))
    response = client.post(
        "/chat",
        json={
            "session_id": "api-session",
            "user_id": "api-user",
            "message": "hello",
            "channel": "api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "api-session"
    assert "reply" in payload
    assert isinstance(payload["tool_results"], list)


def test_chat_endpoint_maps_policy_violation_to_403() -> None:
    workspace = Path("tests/.tmp/api-policy")
    workspace.mkdir(parents=True, exist_ok=True)
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                tool_policy="read_only",
            )
        )
    )
    response = client.post(
        "/chat",
        json={
            "session_id": "api-policy",
            "user_id": "api-user",
            "message": "/tool filesystem.write blocked.txt blocked",
            "channel": "api",
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "policy_violation"


def test_chat_endpoint_maps_tool_argument_validation_to_422() -> None:
    workspace = Path("tests/.tmp/api-validation")
    workspace.mkdir(parents=True, exist_ok=True)
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                allow_process_exec=True,
            )
        )
    )
    response = client.post(
        "/chat",
        json={
            "session_id": "api-validation",
            "user_id": "api-user",
            "message": "/tool shell.exec",
            "channel": "api",
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "tool_argument_validation_error"
