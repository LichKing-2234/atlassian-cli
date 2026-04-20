import typer

from atlassian_cli.output.modes import is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.pr import PullRequestService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket pull request commands")


def build_pr_service(context) -> PullRequestService:
    return PullRequestService(provider=build_provider(context))


@app.command("list")
def list_pull_requests(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    state: str = typer.Option("OPEN", "--state"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    payload = (
        service.list_raw(project_key, repo_slug, state)
        if is_raw_output(output)
        else service.list(project_key, repo_slug, state)
    )
    typer.echo(render_output(payload, output=output))


@app.command("get")
def get_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    payload = (
        service.get_raw(project_key, repo_slug, pr_id)
        if is_raw_output(output)
        else service.get(project_key, repo_slug, pr_id)
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
    output: str = typer.Option("table", "--output"),
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
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    result = (
        service.merge_raw(project_key, repo_slug, pr_id)
        if is_raw_output(output)
        else service.merge(project_key, repo_slug, pr_id)
    )
    typer.echo(render_output(result, output=output))
