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


@app.command("get")
def get_issue(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = service.get_raw(issue_key) if is_raw_output(output) else service.get(issue_key)
    typer.echo(render_output(payload, output=output))


@app.command("search")
def search_issues(
    ctx: typer.Context,
    jql: str = typer.Option(..., "--jql"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    if is_raw_output(output):
        payload = service.search_raw(jql=jql, start=start, limit=limit)
        typer.echo(render_output(payload, output=output))
        return

    if should_use_interactive_output(output, command_kind="collection"):
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

    payload = service.search(jql=jql, start=start, limit=limit)
    typer.echo(render_output(payload, output=output))


@app.command("create")
def create_issue(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project"),
    issue_type: str = typer.Option(..., "--issue-type"),
    summary: str = typer.Option(..., "--summary"),
    description: str = typer.Option("", "--description"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "summary": summary,
        "description": description,
    }
    result = service.create_raw(payload) if is_raw_output(output) else service.create(payload)
    typer.echo(render_output(result, output=output))


@app.command("update")
def update_issue(
    ctx: typer.Context,
    issue_key: str,
    summary: str | None = typer.Option(None, "--summary"),
    description: str | None = typer.Option(None, "--description"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {
        k: v for k, v in {"summary": summary, "description": description}.items() if v is not None
    }
    result = (
        service.update_raw(issue_key, payload)
        if is_raw_output(output)
        else service.update(issue_key, payload)
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
