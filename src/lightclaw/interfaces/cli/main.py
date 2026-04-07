import asyncio
import uuid
from datetime import UTC, datetime

import typer

from lightclaw.domain.jobs.models import JobDefinition
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.domain.errors import LightClawError
from lightclaw.infrastructure.persistence.database import create_session_factory, get_migration_status
from lightclaw.interfaces.common import create_interface_context

cli = typer.Typer(add_completion=False, no_args_is_help=True)
jobs_cli = typer.Typer(add_completion=False, help="Manage scheduled jobs.")
scheduler_cli = typer.Typer(add_completion=False, help="Manage scheduler state.")
skills_cli = typer.Typer(add_completion=False, help="Inspect available skills.")
db_cli = typer.Typer(add_completion=False, help="Manage database initialization and migrations.")
cli.add_typer(jobs_cli, name="jobs")
cli.add_typer(scheduler_cli, name="scheduler")
cli.add_typer(skills_cli, name="skills")
cli.add_typer(db_cli, name="db")


@cli.command()
def chat(
    message: str,
    session_id: str = typer.Option("", help="Existing session id. Auto-generated if omitted."),
    user_id: str = typer.Option("cli-user", help="Logical user id."),
    skills: list[str] = typer.Option(None, "--skill", help="Activate a skill by id."),
) -> None:
    _run_single_turn(
        message=message,
        session_id=session_id,
        user_id=user_id,
        skills=skills or [],
    )


@cli.command()
def repl(
    session_id: str = typer.Option("", help="Existing session id. Auto-generated if omitted."),
    user_id: str = typer.Option("cli-user", help="Logical user id."),
    skills: list[str] = typer.Option(None, "--skill", help="Activate a skill by id."),
) -> None:
    resolved_session_id = session_id or str(uuid.uuid4())
    typer.echo(f"session_id={resolved_session_id}")
    typer.echo("Type '/exit' to quit.")

    while True:
        message = typer.prompt("> ", prompt_suffix="")
        if message.strip() in {"/exit", "/quit"}:
            typer.echo("bye")
            return
        if not message.strip():
            continue
        _run_single_turn(
            message=message,
            session_id=resolved_session_id,
            user_id=user_id,
            skills=skills or [],
        )


def _run_single_turn(message: str, session_id: str, user_id: str, skills: list[str]) -> None:
    settings, container = create_interface_context()
    resolved_session_id = session_id or str(uuid.uuid4())

    async def _run() -> None:
        response = await container.chat_service.chat(
            AgentRequest(
                session_id=resolved_session_id,
                user_id=user_id,
                message=message,
                channel="cli",
                skills=skills,
            )
        )
        typer.echo(f"session_id={resolved_session_id}")
        typer.echo(response.reply)
        if response.tool_results:
            typer.echo("tool_results:")
            for tool_result in response.tool_results:
                typer.echo(f"- {tool_result.name}")
                typer.echo(tool_result.output)

    try:
        asyncio.run(_run())
    except LightClawError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


def run() -> None:
    cli()


@jobs_cli.command("list")
def jobs_list() -> None:
    _settings, container = create_interface_context()

    async def _run() -> None:
        jobs = await container.job_service.list_jobs()
        for job in jobs:
            typer.echo(
                f"{job.job_id} | enabled={job.enabled} | cron={job.cron} | skills={','.join(job.skills) if job.skills else 'none'} | status={job.last_status}"
            )

    asyncio.run(_run())


@jobs_cli.command("create")
def jobs_create(
    job_id: str,
    name: str,
    cron: str,
    input_prompt: str,
    target_channel: str = typer.Option("scheduler"),
    target_destination: str = typer.Option(""),
    skills: list[str] = typer.Option(None, "--skill", help="Activate job skills by id."),
) -> None:
    _settings, container = create_interface_context()

    async def _run() -> None:
        job = JobDefinition(
            job_id=job_id,
            name=name,
            cron=cron,
            input_prompt=input_prompt,
            target_channel=target_channel,
            target_destination=target_destination or None,
            skills=skills or [],
        )
        await container.job_service.upsert_job(job)
        typer.echo(f"created job={job_id}")

    asyncio.run(_run())


@jobs_cli.command("run")
def jobs_run(job_id: str) -> None:
    _settings, container = create_interface_context()

    async def _run() -> None:
        job = await container.job_service.run_job(job_id)
        typer.echo(f"job_id={job.job_id}")
        typer.echo(f"status={job.last_status}")
        typer.echo(job.last_output or "")

    try:
        asyncio.run(_run())
    except LightClawError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@scheduler_cli.command("status")
def scheduler_status() -> None:
    _settings, container = create_interface_context()
    status = container.scheduler_service.status()
    typer.echo(
        f"running={status['running']} poll_seconds={status['poll_seconds']} last_tick={status['last_tick_key']}"
    )


@scheduler_cli.command("tick")
def scheduler_tick() -> None:
    _settings, container = create_interface_context()

    async def _run() -> None:
        jobs = await container.scheduler_service.run_pending_tick(datetime.now(UTC))
        typer.echo(f"executed={len(jobs)}")
        for job in jobs:
            typer.echo(f"{job.job_id} | status={job.last_status}")

    asyncio.run(_run())


@skills_cli.command("list")
def skills_list() -> None:
    _settings, container = create_interface_context()

    async def _run() -> None:
        skills = await container.skill_service.list_skills()
        for skill in skills:
            typer.echo(
                f"{skill.skill_id} | tools={', '.join(skill.tools) if skill.tools else 'none'} | {skill.description}"
            )

    asyncio.run(_run())


@db_cli.command("status")
def db_status() -> None:
    settings, _container = create_interface_context()
    status = get_migration_status(settings.database_url)
    typer.echo(f"database_url={settings.database_url}")
    typer.echo(f"current_version={status['current_version']}")
    typer.echo(f"latest_version={status['latest_version']}")
    typer.echo(
        "pending_versions="
        + (",".join(status["pending_versions"]) if status["pending_versions"] else "none")
    )


@db_cli.command("migrate")
def db_migrate() -> None:
    settings, _container = create_interface_context()
    create_session_factory(settings.database_url)
    status = get_migration_status(settings.database_url)
    typer.echo(f"database_url={settings.database_url}")
    typer.echo(f"current_version={status['current_version']}")
    typer.echo("pending_versions=none")


if __name__ == "__main__":
    run()
