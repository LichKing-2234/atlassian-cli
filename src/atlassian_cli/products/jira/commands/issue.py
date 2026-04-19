import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Jira issue commands")


class IssueService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, issue_key: str) -> dict:
        return self.provider.get_issue(issue_key)


def build_issue_service(context) -> IssueService:
    provider = build_provider(context)
    return IssueService(provider=provider)


@app.command("get")
def get_issue(
    ctx: typer.Context,
    issue_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.get(issue_key), output=output))
