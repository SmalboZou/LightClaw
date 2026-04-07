from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from lightclaw.config.settings import AppSettings
from lightclaw.bootstrap import build_container
from lightclaw.domain.errors import ProviderRequestError
from lightclaw.interfaces.api.app import create_api


def _fresh_workspace(name: str) -> Path:
    workspace = Path(f"tests/.tmp/{name}")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _bootstrap_console(client: TestClient) -> None:
    response = client.post(
        "/console/api/setup/bootstrap",
        json={
            "admin_username": "admin",
            "admin_password": "secret-pass",
            "provider_backend": "mock",
            "provider_model": "mock",
            "provider_base_url": None,
            "provider_api_key": None,
            "storage_backend": "sqlite",
            "tool_policy": "workspace_write",
            "allow_process_exec": False,
            "allow_network_access": False,
        },
    )
    assert response.status_code == 200


def test_health_endpoint() -> None:
    client = TestClient(create_api(AppSettings(storage_backend="memory", provider_backend="mock")))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_endpoint_returns_structured_response() -> None:
    client = TestClient(create_api(AppSettings(storage_backend="memory", provider_backend="mock")))
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
    workspace = _fresh_workspace("api-policy")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                tool_policy="read_only",
                provider_backend="mock",
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
    workspace = _fresh_workspace("api-validation")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                allow_process_exec=True,
                provider_backend="mock",
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


def test_console_index_serves_html() -> None:
    workspace = _fresh_workspace("api-console")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                console_admin_username="",
                console_admin_password="",
                provider_backend="mock",
            )
        )
    )

    response = client.get("/console")

    assert response.status_code == 200
    assert "LightClaw Console" in response.text


def test_console_config_can_be_read_and_saved() -> None:
    workspace = _fresh_workspace("api-console-config")
    env_path = workspace / ".env"
    env_path.write_text("LIGHTCLAW_PROVIDER_BACKEND=mock\n", encoding="utf-8")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                console_admin_username="",
                console_admin_password="",
                provider_backend="mock",
            )
        )
    )
    _bootstrap_console(client)

    read_response = client.get("/console/api/config")
    save_response = client.post(
        "/console/api/config",
        json={
            "provider_backend": "openai_compatible",
            "provider_model": "gpt-4o-mini",
            "provider_base_url": "https://api.openai.com/v1",
            "provider_extra_headers_json": "{\"HTTP-Referer\":\"https://your-app.example\"}",
            "provider_api_key": "sk-test-12345678",
            "storage_backend": "sqlite",
            "tool_policy": "workspace_write",
            "allow_process_exec": False,
            "allow_network_access": False,
        },
    )

    assert read_response.status_code == 200
    assert read_response.json()["provider_backend"] == "mock"
    assert save_response.status_code == 200
    assert save_response.json()["requires_restart"] is False
    env_text = env_path.read_text(encoding="utf-8")
    assert "LIGHTCLAW_PROVIDER_BACKEND=openai_compatible" in env_text
    assert "LIGHTCLAW_PROVIDER_API_KEY=sk-test-12345678" in env_text
    assert (
        "LIGHTCLAW_PROVIDER_EXTRA_HEADERS_JSON={\"HTTP-Referer\": \"https://your-app.example\"}"
        in env_text
    )


def test_console_config_hot_applies_runtime_changes_without_restart() -> None:
    workspace = _fresh_workspace("api-console-hot-reload")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                provider_backend="mock",
                console_admin_username="",
                console_admin_password="",
            )
        )
    )
    _bootstrap_console(client)

    save_response = client.post(
        "/console/api/config",
        json={
            "provider_backend": "mock",
            "provider_model": "hot-reloaded-model",
            "provider_base_url": "",
            "provider_extra_headers_json": "",
            "provider_api_key": "",
            "storage_backend": "sqlite",
            "tool_policy": "workspace_write",
            "allow_process_exec": False,
            "allow_network_access": False,
        },
    )
    chat_response = client.post(
        "/console/api/chat",
        json={
            "session_id": "hot-reload-session",
            "message": "hello",
            "skills": [],
        },
    )

    assert save_response.status_code == 200
    assert save_response.json()["requires_restart"] is False
    assert chat_response.status_code == 200
    assert "reply" in chat_response.json()


def test_console_config_save_keeps_auth_session_alive() -> None:
    workspace = _fresh_workspace("api-console-auth-persist")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                provider_backend="mock",
                console_admin_username="",
                console_admin_password="",
            )
        )
    )
    _bootstrap_console(client)

    save_response = client.post(
        "/console/api/config",
        json={
            "provider_backend": "mock",
            "provider_model": "mock",
            "provider_base_url": "",
            "provider_extra_headers_json": "",
            "provider_api_key": "",
            "storage_backend": "sqlite",
            "tool_policy": "workspace_write",
            "allow_process_exec": False,
            "allow_network_access": False,
        },
    )
    config_response = client.get("/console/api/config")

    assert save_response.status_code == 200
    assert config_response.status_code == 200


def test_console_provider_test_reuses_saved_key_when_input_is_blank() -> None:
    workspace = _fresh_workspace("api-console-provider-fallback")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                provider_backend="openai_compatible",
                provider_model="saved-model",
                provider_base_url="https://api.openai.com/v1",
                provider_api_key="saved-key",
                console_admin_username="",
                console_admin_password="",
            )
        )
    )
    _bootstrap_console(client)

    response = client.post(
        "/console/api/provider/test",
        json={
            "provider_backend": "mock",
            "provider_model": "mock",
            "provider_base_url": "",
            "provider_extra_headers_json": "",
            "provider_api_key": "",
        },
    )

    assert response.status_code == 200


def test_console_provider_test_uses_active_runtime_settings_after_hot_reload() -> None:
    workspace = _fresh_workspace("api-console-provider-hot-runtime")
    settings = AppSettings(
        storage_backend="memory",
        workspace_root=workspace,
        provider_backend="mock",
        console_admin_username="",
        console_admin_password="",
    )
    container = build_container(settings)
    client = TestClient(create_api(settings, container=container))
    _bootstrap_console(client)

    response = client.post(
        "/console/api/provider/test",
        json={
            "provider_backend": "mock",
            "provider_model": "mock",
            "provider_base_url": "",
            "provider_extra_headers_json": "",
            "provider_api_key": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["backend"] == "mock"


def test_console_system_and_sessions_endpoints() -> None:
    workspace = _fresh_workspace("api-console-system")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                console_admin_username="",
                console_admin_password="",
                provider_backend="mock",
            )
        )
    )
    _bootstrap_console(client)
    client.post(
        "/console/api/chat",
        json={
            "session_id": "console-session",
            "message": "hello from console",
            "skills": [],
        },
    )

    system_response = client.get("/console/api/system")
    sessions_response = client.get("/console/api/sessions")
    detail_response = client.get("/console/api/sessions/console-session")

    assert system_response.status_code == 200
    assert system_response.json()["provider_backend"] == "mock"
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["session_id"] == "console-session"
    assert detail_response.status_code == 200
    assert len(detail_response.json()["turns"]) >= 2


def test_console_requires_setup_then_login() -> None:
    workspace = _fresh_workspace("api-console-auth")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                console_admin_username="",
                console_admin_password="",
                provider_backend="mock",
            )
        )
    )

    status_response = client.get("/console/api/setup/status")
    unauthorized_response = client.get("/console/api/config")
    bootstrap_response = client.post(
        "/console/api/setup/bootstrap",
        json={
            "admin_username": "owner",
            "admin_password": "owner-pass",
            "provider_backend": "mock",
            "provider_model": "mock",
            "provider_base_url": None,
            "provider_api_key": None,
            "storage_backend": "sqlite",
            "tool_policy": "workspace_write",
            "allow_process_exec": False,
            "allow_network_access": False,
        },
    )
    me_response = client.get("/console/api/auth/me")
    logout_response = client.post("/console/api/auth/logout")
    login_response = client.post(
        "/console/api/auth/login",
        json={"username": "owner", "password": "owner-pass"},
    )

    assert status_response.status_code == 200
    assert status_response.json()["setup_required"] is True
    assert unauthorized_response.status_code == 401
    assert bootstrap_response.status_code == 200
    assert me_response.json()["authenticated"] is True
    assert logout_response.status_code == 200
    assert login_response.status_code == 200
    assert login_response.json()["authenticated"] is True


def test_console_chat_stream_returns_sse() -> None:
    workspace = _fresh_workspace("api-console-stream")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                console_admin_username="",
                console_admin_password="",
                provider_backend="mock",
            )
        )
    )
    _bootstrap_console(client)

    response = client.post(
        "/console/api/chat/stream",
        json={
            "session_id": "stream-session",
            "message": "hello streaming",
            "skills": [],
        },
    )

    assert response.status_code == 200
    assert "event: delta" in response.text
    assert "event: completed" in response.text


def test_console_user_isolation_for_sessions() -> None:
    workspace = _fresh_workspace("api-console-isolation")
    client = TestClient(
        create_api(
            AppSettings(
                storage_backend="memory",
                workspace_root=workspace,
                console_admin_username="",
                console_admin_password="",
                provider_backend="mock",
            )
        )
    )
    _bootstrap_console(client)
    client.post(
        "/console/api/users",
        json={"username": "operator", "password": "operator-pass", "role": "operator"},
    )
    client.post(
        "/console/api/chat",
        json={
            "session_id": "admin-session",
            "message": "admin note",
            "skills": [],
        },
    )
    client.post("/console/api/auth/logout")
    client.post(
        "/console/api/auth/login",
        json={"username": "operator", "password": "operator-pass"},
    )

    sessions_response = client.get("/console/api/sessions")
    forbidden_response = client.get("/console/api/sessions/admin-session")

    assert sessions_response.status_code == 200
    assert sessions_response.json() == []
    assert forbidden_response.status_code == 403


def test_console_chat_stream_emits_error_event_when_provider_fails() -> None:
    workspace = _fresh_workspace("api-console-stream-error")
    settings = AppSettings(
        storage_backend="memory",
        workspace_root=workspace,
        provider_backend="mock",
        console_admin_username="",
        console_admin_password="",
    )
    container = build_container(settings)
    client = TestClient(create_api(settings, container=container))
    _bootstrap_console(client)

    async def failing_chat(_request):
        raise ProviderRequestError("OpenAI-compatible request failed (429): Rate limit exceeded")

    container.chat_service.chat = failing_chat
    response = client.post(
        "/console/api/chat/stream",
        json={
            "session_id": "stream-error",
            "message": "hello",
            "skills": [],
        },
    )

    assert response.status_code == 200
    assert "event: error" in response.text
