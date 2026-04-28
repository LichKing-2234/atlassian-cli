import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
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
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = service.get_raw(page_id) if is_raw_output(output) else service.get(page_id)
    typer.echo(render_output(payload, output=output))


@app.command("create")
def create_page(
    ctx: typer.Context,
    space_key: str = typer.Option(..., "--space"),
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.create_raw(space_key=space_key, title=title, body=body)
        if is_raw_output(output)
        else service.create(space_key=space_key, title=title, body=body)
    )
    typer.echo(render_output(payload, output=output))


@app.command("update")
def update_page(
    ctx: typer.Context,
    page_id: str,
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.update_raw(page_id, title=title, body=body)
        if is_raw_output(output)
        else service.update(page_id, title=title, body=body)
    )
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_page(
    ctx: typer.Context,
    page_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_page_service(ctx.obj)
    payload = service.delete_raw(page_id) if is_raw_output(output) else service.delete(page_id)
    typer.echo(render_output(payload, output=output))
