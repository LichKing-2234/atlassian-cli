import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.comment import CommentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence comment commands")


def build_comment_service(context) -> CommentService:
    return CommentService(provider=build_provider(context))


def _validate_content_format(content_format: str) -> None:
    if content_format not in {"markdown", "storage"}:
        raise typer.BadParameter(
            "content-format must be markdown or storage on Confluence 6.12.4",
            param_hint="--content-format",
        )


@app.command("list")
def list_comments(
    ctx: typer.Context,
    page_id: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = service.list_raw(page_id) if is_raw_output(output) else service.list(page_id)
    typer.echo(render_output(payload, output=output))


@app.command("add")
def add_comment(
    ctx: typer.Context,
    page_id: str,
    body: str = typer.Option(
        ...,
        "--body",
        help="Comment body. Interpreted as Markdown by default.",
    ),
    content_format: str = typer.Option(
        "markdown",
        "--content-format",
        help="Input format: markdown (default) or storage (raw escape hatch).",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    _validate_content_format(content_format)
    service = build_comment_service(ctx.obj)
    payload = (
        service.add_raw(page_id, body, content_format=content_format)
        if is_raw_output(output)
        else service.add(page_id, body, content_format=content_format)
    )
    typer.echo(render_output(payload, output=output))


@app.command("reply")
def reply_to_comment(
    ctx: typer.Context,
    comment_id: str,
    body: str = typer.Option(
        ...,
        "--body",
        help="Comment body. Interpreted as Markdown by default.",
    ),
    content_format: str = typer.Option(
        "markdown",
        "--content-format",
        help="Input format: markdown (default) or storage (raw escape hatch).",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    _validate_content_format(content_format)
    service = build_comment_service(ctx.obj)
    payload = (
        service.reply_raw(comment_id, body, content_format=content_format)
        if is_raw_output(output)
        else service.reply(comment_id, body, content_format=content_format)
    )
    typer.echo(render_output(payload, output=output))
