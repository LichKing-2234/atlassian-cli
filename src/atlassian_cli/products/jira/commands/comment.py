import typer

from atlassian_cli.compat import StrEnum
from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.comment import CommentService
from atlassian_cli.products.jira.visibility import parse_visibility

app = typer.Typer(help="Jira comment commands")


class JiraBodyFormat(StrEnum):
    MARKDOWN = "markdown"
    JIRA = "jira"


def build_comment_service(context) -> CommentService:
    return CommentService(provider=build_provider(context))


def _parse_visibility(value: str | None) -> dict[str, str] | None:
    try:
        return parse_visibility(value, option_name="--visibility")
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--visibility") from exc


@app.command("add")
def add_comment(
    ctx: typer.Context,
    issue_key: str,
    body: str = typer.Option(..., "--body", help="Comment body; Markdown by default."),
    visibility: str | None = typer.Option(
        None,
        "--visibility",
        help='Jira Core visibility JSON: {"type":"role|group","value":"..."}.',
    ),
    body_format: JiraBodyFormat = typer.Option(
        JiraBodyFormat.MARKDOWN,
        "--body-format",
        help="Input format: markdown (converted) or jira (passed through).",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    parsed_visibility = _parse_visibility(visibility)
    service = build_comment_service(ctx.obj)
    payload = (
        service.add_raw(
            issue_key,
            body,
            visibility=parsed_visibility,
            body_format=body_format.value,
        )
        if is_raw_output(output)
        else service.add(
            issue_key,
            body,
            visibility=parsed_visibility,
            body_format=body_format.value,
        )
    )
    typer.echo(render_output(payload, output=output))


@app.command("edit")
def edit_comment(
    ctx: typer.Context,
    issue_key: str,
    comment_id: str,
    body: str = typer.Option(..., "--body", help="Updated comment body; Markdown by default."),
    visibility: str | None = typer.Option(
        None,
        "--visibility",
        help='Jira Core visibility JSON: {"type":"role|group","value":"..."}.',
    ),
    body_format: JiraBodyFormat = typer.Option(
        JiraBodyFormat.MARKDOWN,
        "--body-format",
        help="Input format: markdown (converted) or jira (passed through).",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    parsed_visibility = _parse_visibility(visibility)
    service = build_comment_service(ctx.obj)
    payload = (
        service.edit_raw(
            issue_key,
            comment_id,
            body,
            visibility=parsed_visibility,
            body_format=body_format.value,
        )
        if is_raw_output(output)
        else service.edit(
            issue_key,
            comment_id,
            body,
            visibility=parsed_visibility,
            body_format=body_format.value,
        )
    )
    typer.echo(render_output(payload, output=output))
