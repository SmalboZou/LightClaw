from typer.testing import CliRunner

from lightclaw.interfaces.cli.main import cli


runner = CliRunner()


def test_cli_chat_command_runs() -> None:
    result = runner.invoke(cli, ["chat", "hello from cli", "--session-id", "cli-test"])

    assert result.exit_code == 0
    assert "session_id=cli-test" in result.stdout
    assert "hello from cli" in result.stdout


def test_cli_chat_shows_tool_results() -> None:
    result = runner.invoke(
        cli,
        ["chat", "/tool echo.text hello-tool", "--session-id", "cli-tool-test"],
    )

    assert result.exit_code == 0
    assert "tool_results:" in result.stdout
    assert "echo.text" in result.stdout


def test_cli_repl_command_exits_cleanly() -> None:
    result = runner.invoke(cli, ["repl", "--session-id", "cli-repl"], input="/exit\n")

    assert result.exit_code == 0
    assert "session_id=cli-repl" in result.stdout
    assert "bye" in result.stdout


def test_cli_skills_list_command_runs() -> None:
    result = runner.invoke(cli, ["skills", "list"])

    assert result.exit_code == 0
    assert "writing_assistant" in result.stdout
