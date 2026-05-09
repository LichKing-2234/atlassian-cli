import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket commit commands")


def build_build_status_service(context) -> BuildStatusService:
    return BuildStatusService(provider=build_provider(context))


@app.command("build-status")
def get_commit_build_status(
    ctx: typer.Context,
    commit: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_build_status_service(ctx.obj)
    payload = (
        service.for_commit_raw(commit) if is_raw_output(output) else service.for_commit(commit)
    )
    typer.echo(render_output(payload, output=output))
