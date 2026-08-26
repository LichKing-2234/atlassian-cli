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
    file_path: str | None = typer.Option(
        None,
        "--file",
        help="Local file path. Provide this or --content-base64, not both.",
    ),
    content_base64: str | None = typer.Option(
        None,
        "--content-base64",
        help="Base64-encoded content. Requires --filename and cannot be used with --file.",
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


@app.command("upload-many")
def upload_attachments(
    ctx: typer.Context,
    content_id: str,
    file_paths: list[str] = typer.Option(..., "--file", help="File path; repeat per file."),
    comment: str | None = typer.Option(None, "--comment"),
    minor_edit: bool = typer.Option(False, "--minor-edit/--no-minor-edit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.upload_many_raw(content_id, file_paths, comment=comment, minor_edit=minor_edit)
        if is_raw_output(output)
        else service.upload_many(content_id, file_paths, comment=comment, minor_edit=minor_edit)
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


@app.command("delete")
def delete_attachment(
    ctx: typer.Context,
    attachment_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_attachment_service(ctx.obj)
    payload = (
        service.delete_raw(attachment_id)
        if is_raw_output(output)
        else service.delete(attachment_id)
    )
    typer.echo(render_output(payload, output=output))
