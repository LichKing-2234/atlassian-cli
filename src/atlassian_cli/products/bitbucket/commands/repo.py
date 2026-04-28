import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.repo import RepoService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket repo commands")


def build_repo_service(context) -> RepoService:
    return RepoService(provider=build_provider(context))


@app.command("get")
def get_repo(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_repo_service(ctx.obj)
    payload = (
        service.get_raw(project_key, repo_slug)
        if is_raw_output(output)
        else service.get(project_key, repo_slug)
    )
    typer.echo(render_output(payload, output=output))


@app.command("list")
def list_repos(
    ctx: typer.Context,
    project_key: str | None = typer.Option(None, "--project"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_repo_service(ctx.obj)
    payload = (
        service.list_raw(project_key=project_key, start=start, limit=limit)
        if is_raw_output(output)
        else service.list(project_key=project_key, start=start, limit=limit)
    )
    typer.echo(render_output(payload, output=output))


@app.command("create")
def create_repo(
    ctx: typer.Context,
    project_key: str = typer.Option(..., "--project"),
    name: str = typer.Option(..., "--name"),
    scm_id: str = typer.Option("git", "--scm-id"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_repo_service(ctx.obj)
    payload = (
        service.create_raw(project_key=project_key, name=name, scm_id=scm_id)
        if is_raw_output(output)
        else service.create(project_key=project_key, name=name, scm_id=scm_id)
    )
    typer.echo(render_output(payload, output=output))
