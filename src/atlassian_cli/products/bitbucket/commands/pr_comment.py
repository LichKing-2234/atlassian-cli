import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.pr_comment import PullRequestCommentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket pull request comment commands")
INLINE_LINE_TYPES = {"ADDED", "REMOVED", "CONTEXT"}


def build_comment_service(context) -> PullRequestCommentService:
    return PullRequestCommentService(provider=build_provider(context))


def _inline_anchor(path: str | None, line: int | None, line_type: str | None) -> dict | None:
    provided = [path is not None, line is not None, line_type is not None]
    if any(provided) and not all(provided):
        raise typer.BadParameter(
            "--path, --line, and --line-type must be supplied together",
            param_hint="--path",
        )
    if not any(provided):
        return None
    if line is None or line <= 0:
        raise typer.BadParameter("--line must be a positive integer", param_hint="--line")

    normalized_line_type = str(line_type).upper()
    if normalized_line_type not in INLINE_LINE_TYPES:
        raise typer.BadParameter(
            "--line-type must be ADDED, REMOVED, or CONTEXT",
            param_hint="--line-type",
        )

    return {"path": path, "line": line, "line_type": normalized_line_type}


@app.command("list")
def list_comments(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.list_raw(project_key, repo_slug, pr_id, start=start, limit=limit)
        if is_raw_output(output)
        else service.list(project_key, repo_slug, pr_id, start=start, limit=limit)
    )
    typer.echo(render_output(payload, output=output))


@app.command("get")
def get_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    comment_id: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.get_raw(project_key, repo_slug, pr_id, comment_id)
        if is_raw_output(output)
        else service.get(project_key, repo_slug, pr_id, comment_id)
    )
    typer.echo(render_output(payload, output=output))


@app.command("add")
def add_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    text: str,
    path: str | None = typer.Option(None, "--path"),
    line: int | None = typer.Option(None, "--line"),
    line_type: str | None = typer.Option(None, "--line-type"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    anchor = _inline_anchor(path, line, line_type)
    service = build_comment_service(ctx.obj)
    payload = (
        service.add_raw(project_key, repo_slug, pr_id, text, anchor=anchor)
        if is_raw_output(output)
        else service.add(project_key, repo_slug, pr_id, text, anchor=anchor)
    )
    typer.echo(render_output(payload, output=output))


@app.command("reply")
def reply_to_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    parent_id: str,
    text: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    payload = (
        service.reply_raw(project_key, repo_slug, pr_id, parent_id, text)
        if is_raw_output(output)
        else service.reply(project_key, repo_slug, pr_id, parent_id, text)
    )
    typer.echo(render_output(payload, output=output))


@app.command("edit")
def edit_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    comment_id: str,
    text: str,
    version: int | None = typer.Option(None, "--version"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if version is None:
        raise typer.BadParameter("--version is required", param_hint="--version")
    service = build_comment_service(ctx.obj)
    payload = (
        service.edit_raw(project_key, repo_slug, pr_id, comment_id, text, version=version)
        if is_raw_output(output)
        else service.edit(project_key, repo_slug, pr_id, comment_id, text, version=version)
    )
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    comment_id: str,
    version: int | None = typer.Option(None, "--version"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if version is None:
        raise typer.BadParameter("--version is required", param_hint="--version")
    service = build_comment_service(ctx.obj)
    payload = (
        service.delete_raw(project_key, repo_slug, pr_id, comment_id, version=version)
        if is_raw_output(output)
        else service.delete(project_key, repo_slug, pr_id, comment_id, version=version)
    )
    typer.echo(render_output(payload, output=output))
