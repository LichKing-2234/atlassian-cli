import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.branch import BranchService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket branch commands")


def build_branch_service(context) -> BranchService:
    return BranchService(provider=build_provider(context))


@app.command("list")
def list_branches(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    filter_text: str | None = typer.Option(None, "--filter"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_branch_service(ctx.obj)
    payload = (
        service.list_raw(project_key, repo_slug, filter_text)
        if is_raw_output(output)
        else service.list(project_key, repo_slug, filter_text)
    )
    typer.echo(render_output(payload, output=output))
