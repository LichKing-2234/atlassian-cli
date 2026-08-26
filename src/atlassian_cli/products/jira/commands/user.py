import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.user import UserService

app = typer.Typer(help="Jira user commands")


def build_user_service(context) -> UserService:
    return UserService(provider=build_provider(context))


@app.command("get")
def get_user(
    ctx: typer.Context,
    username: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_user_service(ctx.obj)
    payload = service.get_raw(username) if is_raw_output(output) else service.get(username)
    typer.echo(render_output(payload, output=output))


@app.command("search")
def search_users(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    project_key: str | None = typer.Option(None, "--project-key", "--project"),
    issue_key: str | None = typer.Option(None, "--issue-key"),
    limit: int = typer.Option(50, "--limit", min=1),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if (project_key is None) == (issue_key is None):
        raise typer.BadParameter("pass exactly one of --project-key or --issue-key")
    service = build_user_service(ctx.obj)
    kwargs = {"project_key": project_key, "issue_key": issue_key, "limit": limit}
    payload = (
        service.search_raw(query, **kwargs)
        if is_raw_output(output)
        else service.search(query, **kwargs)
    )
    typer.echo(render_output(payload, output=output))
