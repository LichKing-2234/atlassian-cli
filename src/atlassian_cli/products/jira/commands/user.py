import typer

from atlassian_cli.output.modes import is_raw_output
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
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_user_service(ctx.obj)
    payload = service.get_raw(username) if is_raw_output(output) else service.get(username)
    typer.echo(render_output(payload, output=output))


@app.command("search")
def search_users(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_user_service(ctx.obj)
    payload = service.search_raw(query) if is_raw_output(output) else service.search(query)
    typer.echo(render_output(payload, output=output))
