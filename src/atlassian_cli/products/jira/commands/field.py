import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.field import FieldService

app = typer.Typer(help="Jira field commands")


def build_field_service(context) -> FieldService:
    return FieldService(provider=build_provider(context))


@app.command("search")
def search_fields(
    ctx: typer.Context,
    query: str = typer.Option("", "--query"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_field_service(ctx.obj)
    payload = service.search_raw(query) if is_raw_output(output) else service.search(query)
    typer.echo(render_output(payload, output=output))


@app.command("options")
def get_field_options(
    ctx: typer.Context,
    field_id: str,
    project_key: str = typer.Option(..., "--project"),
    issue_type: str = typer.Option(..., "--issue-type"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_field_service(ctx.obj)
    payload = (
        service.options_raw(field_id, project_key=project_key, issue_type=issue_type)
        if is_raw_output(output)
        else service.options(field_id, project_key=project_key, issue_type=issue_type)
    )
    typer.echo(render_output(payload, output=output))
