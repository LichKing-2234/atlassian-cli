import json

import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.link import IssueLinkService

app = typer.Typer(help="Jira issue link commands")


def build_issue_link_service(context) -> IssueLinkService:
    return IssueLinkService(provider=build_provider(context))


def _parse_comment_visibility(value: str | None) -> dict | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"invalid JSON for --comment-visibility: {exc.msg}",
            param_hint="--comment-visibility",
        ) from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter(
            "--comment-visibility must be a JSON object",
            param_hint="--comment-visibility",
        )
    visibility_type = parsed.get("type")
    visibility_value = parsed.get("value")
    if not isinstance(visibility_type, str) or not isinstance(visibility_value, str):
        raise typer.BadParameter(
            "--comment-visibility must contain string type and value fields",
            param_hint="--comment-visibility",
        )
    if not visibility_type.strip() or not visibility_value.strip():
        raise typer.BadParameter(
            "--comment-visibility must contain string type and value fields",
            param_hint="--comment-visibility",
        )
    return {"type": visibility_type, "value": visibility_value}


@app.command("create")
def create_issue_link(
    ctx: typer.Context,
    inward_issue: str = typer.Option(..., "--inward", help="Issue key mapped to Jira inwardIssue"),
    outward_issue: str = typer.Option(
        ..., "--outward", help="Issue key mapped to Jira outwardIssue"
    ),
    link_type: str = typer.Option(..., "--type", help="Jira issue link type name"),
    comment: str | None = typer.Option(None, "--comment"),
    comment_visibility: str | None = typer.Option(
        None,
        "--comment-visibility",
        help="Jira comment visibility JSON with type and value fields.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_link_service(ctx.obj)
    kwargs = {
        "inward_issue": inward_issue,
        "outward_issue": outward_issue,
        "link_type": link_type,
        "comment": comment,
        "comment_visibility": _parse_comment_visibility(comment_visibility),
    }
    payload = service.create_raw(**kwargs) if is_raw_output(output) else service.create(**kwargs)
    typer.echo(render_output(payload, output=output))


@app.command("list")
def list_issue_links(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_link_service(ctx.obj)
    payload = service.list_raw(issue_key) if is_raw_output(output) else service.list(issue_key)
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_issue_link(
    ctx: typer.Context,
    link_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_issue_link_service(ctx.obj)
    payload = service.delete_raw(link_id) if is_raw_output(output) else service.delete(link_id)
    typer.echo(render_output(payload, output=output))


@app.command("types")
def list_issue_link_types(
    ctx: typer.Context,
    name_filter: str | None = typer.Option(
        None,
        "--name-filter",
        help="Filter link types by name substring (case-insensitive).",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_link_service(ctx.obj)
    payload = (
        service.types_raw(name_filter=name_filter)
        if is_raw_output(output)
        else service.types(name_filter=name_filter)
    )
    typer.echo(render_output(payload, output=output))
