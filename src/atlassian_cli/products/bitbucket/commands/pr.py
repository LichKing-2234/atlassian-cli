from functools import partial

import typer

from atlassian_cli.output.interactive import InteractiveCollectionSource, browse_collection
from atlassian_cli.output.modes import OutputMode, is_raw_output, normalized_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.output.tty import should_use_color_output, should_use_interactive_output
from atlassian_cli.products.bitbucket.browser import (
    render_pull_request_detail,
    render_pull_request_item,
    render_pull_request_preview,
)
from atlassian_cli.products.bitbucket.commands.pr_comment import app as pr_comment_app
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService
from atlassian_cli.products.bitbucket.services.pr import PullRequestService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket pull request commands")
app.add_typer(pr_comment_app, name="comment")


def build_pr_service(context) -> PullRequestService:
    return PullRequestService(provider=build_provider(context))


def build_build_status_service(context) -> BuildStatusService:
    return BuildStatusService(provider=build_provider(context))


@app.command("list")
def list_pull_requests(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    state: str = typer.Option("OPEN", "--state"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    if is_raw_output(output):
        payload = service.list_raw(project_key, repo_slug, state, start=start, limit=limit)
        typer.echo(render_output(payload, output=output))
        return

    if should_use_interactive_output(output, command_kind="collection"):
        try:
            browse_collection(
                InteractiveCollectionSource(
                    title="Bitbucket pull requests",
                    page_size=limit,
                    fetch_page=lambda page_start, page_limit: service.list_page(
                        project_key, repo_slug, state, page_start, page_limit
                    ),
                    fetch_detail=lambda item: service.get_detail(
                        project_key, repo_slug, item["id"]
                    ),
                    render_item=render_pull_request_item,
                    render_preview=render_pull_request_preview,
                    render_detail=partial(render_pull_request_detail, colorize_diff=True),
                    filter_text=lambda item: "\n".join(
                        [render_pull_request_item(0, item), render_pull_request_preview(item)]
                    ),
                )
            )
            return
        except (ImportError, RuntimeError):
            pass

    payload = service.list(project_key, repo_slug, state, start=start, limit=limit)
    typer.echo(render_output(payload, output=output))


@app.command("get")
def get_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    payload = (
        service.get_raw(project_key, repo_slug, pr_id)
        if is_raw_output(output)
        else service.get(project_key, repo_slug, pr_id)
    )
    typer.echo(render_output(payload, output=output))


@app.command("diff")
def get_pull_request_diff(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    if is_raw_output(output):
        typer.echo(render_output(service.diff_raw(project_key, repo_slug, pr_id), output=output))
        return

    payload = service.get_detail(project_key, repo_slug, pr_id)
    if normalized_output(output) == OutputMode.MARKDOWN:
        typer.echo(
            render_pull_request_detail(
                payload,
                colorize_diff=should_use_color_output(output),
            )
        )
        return

    typer.echo(render_output(payload, output=output))


@app.command("build-status")
def get_pull_request_build_status(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    latest_only: bool = typer.Option(False, "--latest-only"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_build_status_service(ctx.obj)
    payload = (
        service.for_pull_request_raw(
            project_key,
            repo_slug,
            pr_id,
            latest_only=latest_only,
        )
        if is_raw_output(output)
        else service.for_pull_request(
            project_key,
            repo_slug,
            pr_id,
            latest_only=latest_only,
        )
    )
    typer.echo(render_output(payload, output=output))


@app.command("create")
def create_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option("", "--description"),
    from_ref: str = typer.Option(..., "--from-ref"),
    to_ref: str = typer.Option(..., "--to-ref"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    payload = {
        "title": title,
        "description": description,
        "fromRef": {"id": from_ref},
        "toRef": {"id": to_ref},
    }
    service = build_pr_service(ctx.obj)
    result = (
        service.create_raw(project_key, repo_slug, payload)
        if is_raw_output(output)
        else service.create(project_key, repo_slug, payload)
    )
    typer.echo(render_output(result, output=output))


@app.command("merge")
def merge_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    result = (
        service.merge_raw(project_key, repo_slug, pr_id)
        if is_raw_output(output)
        else service.merge(project_key, repo_slug, pr_id)
    )
    typer.echo(render_output(result, output=output))
