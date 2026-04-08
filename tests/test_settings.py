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
