import os
from pathlib import Path
import shutil

from lightclaw.config.settings import AppSettings


def test_app_settings_reads_dotenv_by_default() -> None:
    workspace = Path("tests/.tmp/settings-default-dotenv")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    env_path = workspace / ".env"
    env_path.write_text(
        "LIGHTCLAW_PROVIDER_BACKEND=mock\nLIGHTCLAW_PROVIDER_MODEL=dotenv-model\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        settings = AppSettings(workspace_root=workspace)
        assert settings.provider_model == "dotenv-model"
    finally:
        os.chdir(previous_cwd)
        shutil.rmtree(workspace, ignore_errors=True)


def test_app_settings_reads_browser_configuration() -> None:
    workspace = Path("tests/.tmp/settings-browser-dotenv")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    env_path = workspace / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LIGHTCLAW_PROVIDER_BACKEND=mock",
                "LIGHTCLAW_BROWSER_ENABLED=true",
                "LIGHTCLAW_BROWSER_BACKEND=mock",
                "LIGHTCLAW_BROWSER_HEADLESS=false",
                "LIGHTCLAW_BROWSER_ALLOWED_DOMAINS=wttr.in,mail.google.com",
                "LIGHTCLAW_BROWSER_ALLOW_PERSISTENT_AUTH=true",
                "LIGHTCLAW_BROWSER_PROFILE_ROOT=.profiles/browser",
                "LIGHTCLAW_MAIL_WEB_PROVIDER=gmail",
                "LIGHTCLAW_WEATHER_URL_TEMPLATE=https://wttr.in/{location}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        settings = AppSettings(workspace_root=workspace)
        assert settings.browser_enabled is True
        assert settings.browser_headless is False
        assert settings.browser_allowed_domains == ["wttr.in", "mail.google.com"]
        assert settings.browser_allow_persistent_auth is True
        assert settings.mail_web_provider == "gmail"
        assert settings.weather_url_template == "https://wttr.in/{location}"
        assert settings.browser_profile_root == Path(".profiles/browser").resolve()
    finally:
        os.chdir(previous_cwd)
        shutil.rmtree(workspace, ignore_errors=True)
