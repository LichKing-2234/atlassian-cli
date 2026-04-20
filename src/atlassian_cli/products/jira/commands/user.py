import typer

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
    typer.echo(render_output(service.get(username), output=output))


@app.command("search")
def search_users(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_user_service(ctx.obj)
    typer.echo(render_output(service.search(query), output=output))
