import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.comment import CommentService

app = typer.Typer(help="Jira comment commands")


def build_comment_service(context) -> CommentService:
    return CommentService(provider=build_provider(context))


@app.command("add")
def add_comment(
    ctx: typer.Context,
    issue_key: str,
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.add_raw(issue_key, body) if is_raw_output(output) else service.add(issue_key, body)
    )
    typer.echo(render_output(payload, output=output))


@app.command("edit")
def edit_comment(
    ctx: typer.Context,
    issue_key: str,
    comment_id: str,
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.edit_raw(issue_key, comment_id, body)
        if is_raw_output(output)
        else service.edit(issue_key, comment_id, body)
    )
    typer.echo(render_output(payload, output=output))
