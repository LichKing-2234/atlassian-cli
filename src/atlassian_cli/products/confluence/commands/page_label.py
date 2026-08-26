import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.label import LabelService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page label commands")


def build_label_service(context) -> LabelService:
    return LabelService(provider=build_provider(context))


@app.command("list", help="List labels on a Confluence page.")
def list_labels(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Confluence page ID."),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_label_service(ctx.obj)
    payload = service.list_raw(page_id) if is_raw_output(output) else service.list(page_id)
    typer.echo(render_output(payload, output=output))


@app.command("add", help="Add a label to a Confluence page and read back the labels.")
def add_label(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Confluence page ID."),
    name: str = typer.Option(..., "--name", help="Label name to add."),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_label_service(ctx.obj)
    payload = (
        service.add_raw(page_id, name) if is_raw_output(output) else service.add(page_id, name)
    )
    typer.echo(render_output(payload, output=output))
