import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.restriction import RestrictionService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page restriction commands")


def build_restriction_service(context) -> RestrictionService:
    return RestrictionService(provider=build_provider(context))


@app.command("get", help="Read page view and edit restrictions without changing access.")
def get_restrictions(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Confluence page ID."),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_restriction_service(ctx.obj)
    payload = service.get_raw(page_id) if is_raw_output(output) else service.get(page_id)
    typer.echo(render_output(payload, output=output))
