import typer

from atlassian_cli.output.modes import is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.project import ProjectService

app = typer.Typer(help="Jira project commands")


def build_project_service(context) -> ProjectService:
    return ProjectService(provider=build_provider(context))


@app.command("list")
def list_projects(ctx: typer.Context, output: str = typer.Option("table", "--output")) -> None:
    service = build_project_service(ctx.obj)
    payload = service.list_raw() if is_raw_output(output) else service.list()
    typer.echo(render_output(payload, output=output))


@app.command("get")
def get_project(
    ctx: typer.Context,
    project_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_project_service(ctx.obj)
    payload = service.get_raw(project_key) if is_raw_output(output) else service.get(project_key)
    typer.echo(render_output(payload, output=output))
