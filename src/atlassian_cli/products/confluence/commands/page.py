import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.page import PageService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page commands")


def build_page_service(context) -> PageService:
    return PageService(provider=build_provider(context))


@app.command("get")
def get_page(
    ctx: typer.Context,
    page_id: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.get(page_id), output=output))


@app.command("create")
def create_page(
    ctx: typer.Context,
    space_key: str = typer.Option(..., "--space"),
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.create(space_key=space_key, title=title, body=body), output=output))


@app.command("update")
def update_page(
    ctx: typer.Context,
    page_id: str,
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.update(page_id, title=title, body=body), output=output))


@app.command("delete")
def delete_page(
    ctx: typer.Context,
    page_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: str = typer.Option("table", "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.delete(page_id), output=output))
