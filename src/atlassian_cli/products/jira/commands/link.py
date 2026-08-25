import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.link import IssueLinkService

app = typer.Typer(help="Jira issue link commands")


def build_issue_link_service(context) -> IssueLinkService:
    return IssueLinkService(provider=build_provider(context))


@app.command("create")
def create_issue_link(
    ctx: typer.Context,
    inward_issue: str = typer.Option(..., "--inward", help="Issue key mapped to Jira inwardIssue"),
    outward_issue: str = typer.Option(
        ..., "--outward", help="Issue key mapped to Jira outwardIssue"
    ),
    link_type: str = typer.Option(..., "--type", help="Jira issue link type name"),
    comment: str | None = typer.Option(None, "--comment"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_link_service(ctx.obj)
    kwargs = {
        "inward_issue": inward_issue,
        "outward_issue": outward_issue,
        "link_type": link_type,
        "comment": comment,
    }
    payload = service.create_raw(**kwargs) if is_raw_output(output) else service.create(**kwargs)
    typer.echo(render_output(payload, output=output))


@app.command("list")
def list_issue_links(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_link_service(ctx.obj)
    payload = service.list_raw(issue_key) if is_raw_output(output) else service.list(issue_key)
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_issue_link(
    ctx: typer.Context,
    link_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_issue_link_service(ctx.obj)
    payload = service.delete_raw(link_id) if is_raw_output(output) else service.delete(link_id)
    typer.echo(render_output(payload, output=output))


@app.command("types")
def list_issue_link_types(
    ctx: typer.Context,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_link_service(ctx.obj)
    payload = service.types_raw() if is_raw_output(output) else service.types()
    typer.echo(render_output(payload, output=output))
