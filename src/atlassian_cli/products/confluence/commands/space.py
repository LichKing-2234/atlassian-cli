import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.space import SpaceService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence space commands")


def build_space_service(context) -> SpaceService:
    return SpaceService(provider=build_provider(context))


@app.command("list")
def list_spaces(
    ctx: typer.Context,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_space_service(ctx.obj)
    typer.echo(render_output(service.list(start=start, limit=limit), output=output))


@app.command("get")
def get_space(
    ctx: typer.Context,
    space_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_space_service(ctx.obj)
    typer.echo(render_output(service.get(space_key), output=output))
