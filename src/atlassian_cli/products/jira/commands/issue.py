import typer

from atlassian_cli.output.renderers import render_output
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
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.get(issue_key), output=output))


@app.command("search")
def search_issues(
    ctx: typer.Context,
    jql: str = typer.Option(..., "--jql"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.search(jql=jql, start=start, limit=limit), output=output))


@app.command("create")
def create_issue(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project"),
    issue_type: str = typer.Option(..., "--issue-type"),
    summary: str = typer.Option(..., "--summary"),
    description: str = typer.Option("", "--description"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "summary": summary,
        "description": description,
    }
    typer.echo(render_output(service.create(payload), output=output))


@app.command("update")
def update_issue(
    ctx: typer.Context,
    issue_key: str,
    summary: str | None = typer.Option(None, "--summary"),
    description: str | None = typer.Option(None, "--description"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {k: v for k, v in {"summary": summary, "description": description}.items() if v is not None}
    typer.echo(render_output(service.update(issue_key, payload), output=output))


@app.command("transition")
def transition_issue(
    ctx: typer.Context,
    issue_key: str,
    transition: str = typer.Option(..., "--to"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.transition(issue_key, transition), output=output))
