import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.attachment import AttachmentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page attachment commands")


def build_attachment_service(context) -> AttachmentService:
    return AttachmentService(provider=build_provider(context))


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    page_id: str,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(50, "--limit"),
    filename: str | None = typer.Option(None, "--filename"),
    media_type: str | None = typer.Option(None, "--media-type"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    kwargs = {
        "start": start,
        "limit": limit,
        "filename": filename,
        "media_type": media_type,
    }
    payload = (
        service.list_raw(page_id, **kwargs)
        if is_raw_output(output)
        else service.list(page_id, **kwargs)
    )
    typer.echo(render_output(payload, output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    page_id: str,
    file_path: str,
    comment: str | None = typer.Option(None, "--comment"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.upload_raw(page_id, file_path, comment=comment)
        if is_raw_output(output)
        else service.upload(page_id, file_path, comment=comment)
    )
    typer.echo(render_output(payload, output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    page_id: str,
    name: str = typer.Option(..., "--name"),
    destination: str = typer.Option(..., "--destination"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.download_from_content_raw(page_id, name=name, destination=destination)
        if is_raw_output(output)
        else service.download_from_content(page_id, name=name, destination=destination)
    )
    typer.echo(render_output(payload, output=output))
