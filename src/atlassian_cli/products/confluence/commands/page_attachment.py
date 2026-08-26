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
    file_path: str | None = typer.Argument(
        None,
        metavar="[FILE_PATH]",
        help="Local file path. Provide this or --content-base64, not both.",
    ),
    content_base64: str | None = typer.Option(
        None,
        "--content-base64",
        help="Base64-encoded content. Requires --filename and cannot be used with FILE_PATH.",
    ),
    filename: str | None = typer.Option(
        None,
        "--filename",
        help="Attachment filename required with --content-base64.",
    ),
    comment: str | None = typer.Option(
        None,
        "--comment",
        help="Comment recorded in the attachment history.",
    ),
    minor_edit: bool = typer.Option(
        False,
        "--minor-edit/--no-minor-edit",
        help="Mark the upload as a minor edit. Defaults to false.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    kwargs = {
        "content_base64": content_base64,
        "filename": filename,
        "comment": comment,
        "minor_edit": minor_edit,
    }
    try:
        payload = (
            service.upload_raw(page_id, file_path, **kwargs)
            if is_raw_output(output)
            else service.upload(page_id, file_path, **kwargs)
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
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
