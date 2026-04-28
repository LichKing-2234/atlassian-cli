import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
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
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = service.list_raw(page_id) if is_raw_output(output) else service.list(page_id)
    typer.echo(render_output(payload, output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    page_id: str,
    file_path: str = typer.Option(..., "--file"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.upload_raw(page_id, file_path)
        if is_raw_output(output)
        else service.upload(page_id, file_path)
    )
    typer.echo(render_output(payload, output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    attachment_id: str,
    destination: str = typer.Option(..., "--destination"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.download_raw(attachment_id, destination)
        if is_raw_output(output)
        else service.download(attachment_id, destination)
    )
    typer.echo(render_output(payload, output=output))
