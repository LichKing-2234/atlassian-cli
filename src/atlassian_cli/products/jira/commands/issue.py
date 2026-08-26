import json
from pathlib import Path

import typer

from atlassian_cli.compat import StrEnum
from atlassian_cli.output.interactive import InteractiveCollectionSource, browse_collection
from atlassian_cli.output.markdown import (
    render_markdown,
    render_markdown_list_item,
    render_markdown_preview,
)
from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.output.tty import should_use_interactive_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.commands.attachment import app as attachment_app
from atlassian_cli.products.jira.commands.link import app as link_app
from atlassian_cli.products.jira.services.issue import IssueService
from atlassian_cli.products.jira.visibility import parse_visibility

app = typer.Typer(help="Jira issue commands")
watcher_app = typer.Typer(help="Jira issue watcher commands")
worklog_app = typer.Typer(help="Jira issue worklog commands")
app.add_typer(attachment_app, name="attachment")
app.add_typer(link_app, name="link")
app.add_typer(watcher_app, name="watcher")
app.add_typer(worklog_app, name="worklog")


def build_issue_service(context) -> IssueService:
    provider = build_provider(context)
    return IssueService(provider=provider)


DEFAULT_ISSUE_FIELDS = "summary,status,assignee,reporter,priority"


class JiraDescriptionFormat(StrEnum):
    MARKDOWN = "markdown"
    JIRA = "jira"


def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    values = [item.strip() for item in value.split(",") if item.strip()]
    return values or None


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise typer.BadParameter(f"invalid boolean value: {value}")


def _parse_json_object(value: str | None, *, option_name: str) -> dict:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"invalid JSON for {option_name}: {exc.msg}", param_hint=option_name
        ) from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter(f"{option_name} must be a JSON object", param_hint=option_name)
    return parsed


def _parse_attachments(value: str | None) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(parsed, list):
        raise typer.BadParameter(
            "--attachments must be a JSON array or CSV", param_hint="--attachments"
        )
    return [str(item) for item in parsed]


def _load_batch_issues(*, issues_json: str | None, file_path: str | None) -> list[dict]:
    if issues_json:
        try:
            parsed = json.loads(issues_json)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                f"invalid JSON for --issues: {exc.msg}", param_hint="--issues"
            ) from exc
        if not isinstance(parsed, list):
            raise typer.BadParameter("--issues must be a JSON array", param_hint="--issues")
        return parsed
    if file_path is None:
        raise typer.BadParameter("pass --issues or --file")
    try:
        parsed = json.loads(Path(file_path).read_text())
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"file not found: {file_path}", param_hint="--file") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"invalid JSON in {file_path}: {exc.msg}", param_hint="--file"
        ) from exc
    if not isinstance(parsed, list):
        raise typer.BadParameter(
            "batch create input must be a JSON array of issues", param_hint="--file"
        )
    return parsed


@app.command("get")
def get_issue(
    ctx: typer.Context,
    issue_key: str,
    fields: str = typer.Option(DEFAULT_ISSUE_FIELDS, "--fields"),
    expand: str | None = typer.Option(None, "--expand"),
    comment_limit: int = typer.Option(10, "--comment-limit", min=0, max=100),
    properties: str | None = typer.Option(None, "--properties"),
    update_history: str = typer.Option("true", "--update-history"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    use_default_read = (
        fields == DEFAULT_ISSUE_FIELDS
        and expand is None
        and comment_limit == 10
        and properties is None
        and _parse_bool(update_history) is True
    )
    if is_raw_output(output):
        payload = (
            service.get_raw(issue_key)
            if use_default_read
            else service.get_raw(
                issue_key,
                fields=_parse_csv(fields),
                expand=expand,
                comment_limit=comment_limit,
                properties=_parse_csv(properties),
                update_history=_parse_bool(update_history),
            )
        )
    else:
        payload = (
            service.get(issue_key)
            if use_default_read
            else service.get(
                issue_key,
                fields=_parse_csv(fields),
                expand=expand,
                comment_limit=comment_limit,
                properties=_parse_csv(properties),
                update_history=_parse_bool(update_history),
            )
        )
    typer.echo(render_output(payload, output=output))


@app.command("search")
def search_issues(
    ctx: typer.Context,
    jql: str = typer.Option(..., "--jql"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    fields: str = typer.Option(DEFAULT_ISSUE_FIELDS, "--fields"),
    expand: str | None = typer.Option(None, "--expand"),
    projects_filter: str | None = typer.Option(None, "--projects-filter"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    use_default_search = (
        fields == DEFAULT_ISSUE_FIELDS and expand is None and projects_filter is None
    )
    if is_raw_output(output):
        payload = (
            service.search_raw(jql=jql, start=start, limit=limit)
            if use_default_search
            else service.search_raw(
                jql=jql,
                start=start,
                limit=limit,
                fields=_parse_csv(fields),
                expand=expand,
                projects_filter=_parse_csv(projects_filter),
            )
        )
        typer.echo(render_output(payload, output=output))
        return

    if should_use_interactive_output(output, command_kind="collection"):
        try:
            browse_collection(
                InteractiveCollectionSource(
                    title="Jira issue search",
                    page_size=limit,
                    fetch_page=lambda page_start, page_limit: service.search_page(
                        jql, page_start, page_limit
                    ),
                    fetch_detail=lambda item: service.get(item["key"]),
                    render_item=lambda index, item: render_markdown_list_item(item),
                    render_preview=render_markdown_preview,
                    render_detail=render_markdown,
                    filter_text=lambda item: "\n".join(
                        [render_markdown_list_item(item), render_markdown_preview(item)]
                    ),
                )
            )
            return
        except (ImportError, RuntimeError):
            pass

    payload = (
        service.search(jql=jql, start=start, limit=limit)
        if use_default_search
        else service.search(
            jql=jql,
            start=start,
            limit=limit,
            fields=_parse_csv(fields),
            expand=expand,
            projects_filter=_parse_csv(projects_filter),
        )
    )
    typer.echo(render_output(payload, output=output))


@app.command("create")
def create_issue(
    ctx: typer.Context,
    project_key: str = typer.Option(
        ..., "--project-key", "--project", help="Jira project key, for example DEMO."
    ),
    issue_type: str = typer.Option(
        ..., "--issue-type", help="Issue type configured for the project."
    ),
    summary: str = typer.Option(..., "--summary", help="Issue summary/title."),
    assignee: str | None = typer.Option(None, "--assignee", help="Optional Jira Server username."),
    description: str | None = typer.Option(
        None, "--description", help="Issue description; Markdown by default."
    ),
    description_format: JiraDescriptionFormat = typer.Option(
        JiraDescriptionFormat.MARKDOWN,
        "--description-format",
        help="Description input format; use jira to preserve Jira wiki markup.",
    ),
    components: str | None = typer.Option(
        None, "--components", help="Optional comma-separated component names."
    ),
    additional_fields: str | None = typer.Option(
        None,
        "--additional-fields",
        help="Optional JSON object of deployment-specific Jira fields.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    parsed_components = _parse_csv(components)
    parsed_additional_fields = _parse_json_object(
        additional_fields, option_name="--additional-fields"
    )
    kwargs = {
        "project_key": project_key,
        "summary": summary,
        "issue_type": issue_type,
        "assignee": assignee,
        "description": description,
        "description_format": description_format.value,
        "components": parsed_components,
        "additional_fields": parsed_additional_fields,
    }
    result = service.create_raw(**kwargs) if is_raw_output(output) else service.create(**kwargs)
    typer.echo(render_output(result, output=output))


@app.command("update")
def update_issue(
    ctx: typer.Context,
    issue_key: str,
    fields: str | None = typer.Option(None, "--fields"),
    additional_fields: str | None = typer.Option(None, "--additional-fields"),
    components: str | None = typer.Option(None, "--components"),
    attachments: str | None = typer.Option(None, "--attachments"),
    transition: str | None = typer.Option(None, "--transition"),
    comment: str | None = typer.Option(None, "--comment"),
    comment_visibility: str | None = typer.Option(None, "--comment-visibility"),
    worklog: str | None = typer.Option(None, "--worklog"),
    worklog_started: str | None = typer.Option(None, "--worklog-started"),
    description_format: JiraDescriptionFormat = typer.Option(
        JiraDescriptionFormat.MARKDOWN, "--description-format"
    ),
    comment_format: JiraDescriptionFormat = typer.Option(
        JiraDescriptionFormat.MARKDOWN, "--comment-format"
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    parsed_fields = _parse_json_object(fields, option_name="--fields")
    parsed_additional_fields = _parse_json_object(
        additional_fields, option_name="--additional-fields"
    )
    parsed_components = _parse_csv(components)
    parsed_attachments = _parse_attachments(attachments)
    try:
        parsed_visibility = parse_visibility(comment_visibility, option_name="--comment-visibility")
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--comment-visibility") from exc
    kwargs = {
        "fields": parsed_fields,
        "additional_fields": parsed_additional_fields,
        "components": parsed_components,
        "attachments": parsed_attachments,
        "transition": transition,
        "comment": comment,
        "comment_format": comment_format.value,
        "comment_visibility": parsed_visibility,
        "worklog": worklog,
        "worklog_started": worklog_started,
        "description_format": description_format.value,
    }
    result = (
        service.update_raw(issue_key, **kwargs)
        if is_raw_output(output)
        else service.update(issue_key, **kwargs)
    )
    typer.echo(render_output(result, output=output))


@app.command("assign")
def assign_issue(
    ctx: typer.Context,
    issue_key: str,
    assignee: str | None = typer.Option(
        None, "--assignee", help="Jira username or user JSON; omit to unassign."
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    result = (
        service.assign_raw(issue_key, assignee)
        if is_raw_output(output)
        else service.assign(issue_key, assignee)
    )
    typer.echo(render_output(result, output=output))


@app.command("transition")
def transition_issue(
    ctx: typer.Context,
    issue_key: str,
    transition: str = typer.Option(..., "--transition-id", "--to"),
    fields: str | None = typer.Option(None, "--fields"),
    comment: str | None = typer.Option(None, "--comment"),
    comment_format: JiraDescriptionFormat = typer.Option(
        JiraDescriptionFormat.MARKDOWN, "--comment-format"
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    kwargs = {
        "fields": _parse_json_object(fields, option_name="--fields"),
        "comment": comment,
        "comment_format": comment_format.value,
    }
    result = (
        service.transition_raw(issue_key, transition, **kwargs)
        if is_raw_output(output)
        else service.transition(issue_key, transition, **kwargs)
    )
    typer.echo(render_output(result, output=output))


@app.command("reparent-subtask")
def reparent_subtask(
    ctx: typer.Context,
    issue_key: str,
    parent_key: str = typer.Option(..., "--parent", help="Destination parent issue key."),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    """Move a sub-task to a different parent on Jira Server 7.11.0 build 711000."""
    result = build_issue_service(ctx.obj).reparent_subtask(issue_key, parent_key)
    typer.echo(render_output(result, output=output))


@app.command("transitions")
def get_transitions(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = (
        service.get_transitions_raw(issue_key)
        if is_raw_output(output)
        else service.get_transitions(issue_key)
    )
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_issue(
    ctx: typer.Context,
    issue_key: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_issue_service(ctx.obj)
    payload = service.delete_raw(issue_key) if is_raw_output(output) else service.delete(issue_key)
    typer.echo(render_output(payload, output=output))


@app.command("batch-create")
def batch_create_issues(
    ctx: typer.Context,
    issues_json: str | None = typer.Option(
        None,
        "--issues",
        help=(
            "JSON array of semantic objects requiring project_key, summary, and issue_type; "
            "description, assignee, components, description_format, and additional Jira "
            "fields are optional. Legacy Jira REST-shaped objects remain accepted unchanged."
        ),
    ),
    file_path: str | None = typer.Option(
        None, "--file", help="Read the same semantic issue array from a JSON file."
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="Validate and prepare every issue without creating anything.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    issues = _load_batch_issues(issues_json=issues_json, file_path=file_path)
    service = build_issue_service(ctx.obj)
    if is_raw_output(output):
        payload = service.batch_create_raw(issues, validate_only=validate_only)
    else:
        payload = service.batch_create(issues, validate_only=validate_only)
    typer.echo(render_output(payload, output=output))


@watcher_app.command("list")
def list_watchers(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = (
        service.get_watchers_raw(issue_key)
        if is_raw_output(output)
        else service.get_watchers(issue_key)
    )
    typer.echo(render_output(payload, output=output))


@watcher_app.command("add")
def add_watcher(
    ctx: typer.Context,
    issue_key: str,
    user_identifier: str = typer.Option(
        ...,
        "--user-identifier",
        help="Jira Server username to add; Cloud account IDs are not supported.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = (
        service.add_watcher_raw(issue_key, user_identifier)
        if is_raw_output(output)
        else service.add_watcher(issue_key, user_identifier)
    )
    typer.echo(render_output(payload, output=output))


@watcher_app.command("remove")
def remove_watcher(
    ctx: typer.Context,
    issue_key: str,
    username: str = typer.Option(
        ...,
        "--username",
        help="Jira Server username to remove; Cloud account IDs are not supported.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = (
        service.remove_watcher_raw(issue_key, username)
        if is_raw_output(output)
        else service.remove_watcher(issue_key, username)
    )
    typer.echo(render_output(payload, output=output))


@worklog_app.command("list")
def list_worklogs(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = (
        service.get_worklogs_raw(issue_key)
        if is_raw_output(output)
        else service.get_worklogs(issue_key)
    )
    typer.echo(render_output(payload, output=output))


@worklog_app.command("add")
def add_worklog(
    ctx: typer.Context,
    issue_key: str,
    time_spent: str = typer.Option(..., "--time-spent", help="Time spent in Jira format."),
    comment: str | None = typer.Option(
        None, "--comment", help="Worklog comment; Markdown by default."
    ),
    started: str | None = typer.Option(None, "--started", help="Work start time in ISO format."),
    original_estimate: str | None = typer.Option(
        None, "--original-estimate", help="New original estimate for the issue."
    ),
    remaining_estimate: str | None = typer.Option(
        None, "--remaining-estimate", help="New remaining estimate after logging work."
    ),
    comment_format: JiraDescriptionFormat = typer.Option(
        JiraDescriptionFormat.MARKDOWN,
        "--comment-format",
        help="Comment input format: markdown (converted) or jira (passed through).",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    kwargs = {
        "comment": comment,
        "comment_format": comment_format.value,
        "started": started,
        "original_estimate": original_estimate,
        "remaining_estimate": remaining_estimate,
    }
    payload = (
        service.add_worklog_raw(issue_key, time_spent, **kwargs)
        if is_raw_output(output)
        else service.add_worklog(issue_key, time_spent, **kwargs)
    )
    typer.echo(render_output(payload, output=output))


@app.command("changelog-batch")
def batch_get_changelogs(
    issue_keys: list[str] = typer.Option(..., "--issue"),
) -> None:
    del issue_keys
    raise typer.BadParameter("Cloud support is not available in v1")
