import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.attachment import AttachmentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence attachment commands")


def build_attachment_service(context) -> AttachmentService:
    return AttachmentService(provider=build_provider(context))


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    page_id: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    typer.echo(render_output(service.list(page_id), output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    page_id: str,
    file_path: str = typer.Option(..., "--file"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    typer.echo(render_output(service.upload(page_id, file_path), output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    attachment_id: str,
    destination: str = typer.Option(..., "--destination"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    typer.echo(render_output(service.download(attachment_id, destination), output=output))
