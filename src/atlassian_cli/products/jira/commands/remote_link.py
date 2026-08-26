import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.remote_link import RemoteIssueLinkService

app = typer.Typer(help="Jira remote issue link commands")


def build_remote_link_service(context) -> RemoteIssueLinkService:
    return RemoteIssueLinkService(provider=build_provider(context))


@app.command(
    "create",
    help="Create a Jira 7.11 remote issue link, distinct from native Jira issue links.",
)
def create_remote_issue_link(
    ctx: typer.Context,
    issue_key: str,
    url: str = typer.Option(..., "--url", help="Remote link URL."),
    title: str = typer.Option(..., "--title", help="Displayed remote link title."),
    summary: str | None = typer.Option(None, "--summary", help="Optional link description."),
    relationship: str | None = typer.Option(
        None,
        "--relationship",
        help="Optional relationship displayed by Jira.",
    ),
    icon_url: str | None = typer.Option(
        None,
        "--icon-url",
        help="Optional URL for the remote link's 16x16 icon.",
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_remote_link_service(ctx.obj)
    create = service.create_raw if is_raw_output(output) else service.create
    payload = create(
        issue_key,
        url=url,
        title=title,
        summary=summary,
        relationship=relationship,
        icon_url=icon_url,
    )
    typer.echo(render_output(payload, output=output))
