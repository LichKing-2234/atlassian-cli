import json
from pathlib import Path

import typer

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
from atlassian_cli.products.jira.services.issue import IssueService

app = typer.Typer(help="Jira issue commands")


def build_issue_service(context) -> IssueService:
    provider = build_provider(context)
    return IssueService(provider=provider)


DEFAULT_ISSUE_FIELDS = "summary,status,assignee,reporter,priority"


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
    comment_limit: int = typer.Option(10, "--comment-limit"),
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
    project_key: str = typer.Option(..., "--project-key", "--project"),
    issue_type: str = typer.Option(..., "--issue-type"),
    summary: str = typer.Option(..., "--summary"),
    assignee: str | None = typer.Option(None, "--assignee"),
    description: str | None = typer.Option(None, "--description"),
    components: str | None = typer.Option(None, "--components"),
    additional_fields: str | None = typer.Option(None, "--additional-fields"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    if assignee:
        payload["assignee"] = {"name": assignee}
    if description:
        payload["description"] = description
    parsed_components = _parse_csv(components)
    if parsed_components:
        payload["components"] = [{"name": name} for name in parsed_components]
    parsed_additional_fields = _parse_json_object(
        additional_fields, option_name="--additional-fields"
    )
    payload.update(parsed_additional_fields)
    result = (
        service.create_raw(payload)
        if is_raw_output(output)
        else service.create(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            assignee=assignee,
            description=description,
            components=parsed_components,
            additional_fields=parsed_additional_fields,
        )
    )
    typer.echo(render_output(result, output=output))


@app.command("update")
def update_issue(
    ctx: typer.Context,
    issue_key: str,
    fields: str = typer.Option(..., "--fields"),
    additional_fields: str | None = typer.Option(None, "--additional-fields"),
    components: str | None = typer.Option(None, "--components"),
    attachments: str | None = typer.Option(None, "--attachments"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    parsed_fields = _parse_json_object(fields, option_name="--fields")
    parsed_additional_fields = _parse_json_object(
        additional_fields, option_name="--additional-fields"
    )
    parsed_components = _parse_csv(components)
    parsed_attachments = _parse_attachments(attachments)
    payload = {**parsed_fields, **parsed_additional_fields}
    if parsed_components:
        payload["components"] = [{"name": name} for name in parsed_components]
    if parsed_attachments:
        payload["attachments"] = parsed_attachments
    result = (
        service.update_raw(issue_key, payload)
        if is_raw_output(output)
        else service.update(
            issue_key,
            fields=parsed_fields,
            additional_fields=parsed_additional_fields,
            components=parsed_components,
            attachments=parsed_attachments,
        )
    )
    typer.echo(render_output(result, output=output))


@app.command("transition")
def transition_issue(
    ctx: typer.Context,
    issue_key: str,
    transition: str = typer.Option(..., "--to"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    result = (
        service.transition_raw(issue_key, transition)
        if is_raw_output(output)
        else service.transition(issue_key, transition)
    )
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
    issues_json: str | None = typer.Option(None, "--issues"),
    file_path: str | None = typer.Option(None, "--file"),
    validate_only: bool = typer.Option(False, "--validate-only"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if validate_only:
        raise typer.BadParameter(
            "validate-only is not supported on Jira Server/DC", param_hint="--validate-only"
        )
    issues = _load_batch_issues(issues_json=issues_json, file_path=file_path)
    service = build_issue_service(ctx.obj)
    if is_raw_output(output):
        payload = service.batch_create_raw(issues)
    else:
        payload = service.batch_create(issues)
    typer.echo(render_output(payload, output=output))


@app.command("changelog-batch")
def batch_get_changelogs(
    issue_keys: list[str] = typer.Option(..., "--issue"),
) -> None:
    del issue_keys
    raise typer.BadParameter("Cloud support is not available in v1")
