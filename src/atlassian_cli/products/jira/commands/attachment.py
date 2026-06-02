import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.attachment import AttachmentService

app = typer.Typer(help="Jira issue attachment commands")


def build_attachment_service(context) -> AttachmentService:
    return AttachmentService(provider=build_provider(context))


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = service.list_raw(issue_key) if is_raw_output(output) else service.list(issue_key)
    typer.echo(render_output(payload, output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    issue_key: str,
    file_path: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.upload_raw(issue_key, file_path)
        if is_raw_output(output)
        else service.upload(issue_key, file_path)
    )
    typer.echo(render_output(payload, output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    issue_key: str,
    name: str = typer.Option(..., "--name"),
    destination: str = typer.Option(..., "--destination"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.download_raw(issue_key, name=name, destination=destination)
        if is_raw_output(output)
        else service.download(issue_key, name=name, destination=destination)
    )
    typer.echo(render_output(payload, output=output))
