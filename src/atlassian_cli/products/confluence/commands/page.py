import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.page import PageService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page commands")


def build_page_service(context) -> PageService:
    return PageService(provider=build_provider(context))


@app.command("get")
def get_page(
    ctx: typer.Context,
    page_id: str | None = typer.Argument(None),
    title: str | None = typer.Option(None, "--title"),
    space_key: str | None = typer.Option(None, "--space"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    if page_id is not None:
        payload = service.get_raw(page_id) if is_raw_output(output) else service.get(page_id)
    elif title and space_key:
        payload = (
            service.get_by_title_raw(space_key, title)
            if is_raw_output(output)
            else service.get_by_title(space_key, title)
        )
    else:
        raise typer.BadParameter("provide a page id or both --title and --space")
    typer.echo(render_output(payload, output=output))


@app.command("search")
def search_pages(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.search_raw(query, limit=limit)
        if is_raw_output(output)
        else service.search(query, limit=limit)
    )
    typer.echo(render_output(payload, output=output))


@app.command("children")
def get_children(
    ctx: typer.Context,
    page_id: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = service.children_raw(page_id) if is_raw_output(output) else service.children(page_id)
    typer.echo(render_output(payload, output=output))


@app.command("tree")
def get_tree(
    ctx: typer.Context,
    space_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = service.tree_raw(space_key) if is_raw_output(output) else service.tree(space_key)
    typer.echo(render_output(payload, output=output))


@app.command("history")
def get_history(
    ctx: typer.Context,
    page_id: str,
    version: int = typer.Option(..., "--version"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.history_raw(page_id, version=version)
        if is_raw_output(output)
        else service.history(page_id, version=version)
    )
    typer.echo(render_output(payload, output=output))


@app.command("diff")
def get_diff(
    ctx: typer.Context,
    page_id: str,
    from_version: int = typer.Option(..., "--from-version"),
    to_version: int = typer.Option(..., "--to-version"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.diff_raw(page_id, from_version=from_version, to_version=to_version)
        if is_raw_output(output)
        else service.diff(page_id, from_version=from_version, to_version=to_version)
    )
    typer.echo(render_output(payload, output=output))


@app.command("move")
def move_page(
    ctx: typer.Context,
    page_id: str,
    target_parent_id: str | None = typer.Option(None, "--parent"),
    target_space_key: str | None = typer.Option(None, "--space"),
    position: str = typer.Option("append", "--position"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.move_raw(
            page_id,
            target_parent_id=target_parent_id,
            target_space_key=target_space_key,
            position=position,
        )
        if is_raw_output(output)
        else service.move(
            page_id,
            target_parent_id=target_parent_id,
            target_space_key=target_space_key,
            position=position,
        )
    )
    typer.echo(render_output(payload, output=output))


@app.command("create")
def create_page(
    ctx: typer.Context,
    space_key: str = typer.Option(..., "--space"),
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.create_raw(space_key=space_key, title=title, body=body)
        if is_raw_output(output)
        else service.create(space_key=space_key, title=title, body=body)
    )
    typer.echo(render_output(payload, output=output))


@app.command("update")
def update_page(
    ctx: typer.Context,
    page_id: str,
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.update_raw(page_id, title=title, body=body)
        if is_raw_output(output)
        else service.update(page_id, title=title, body=body)
    )
    typer.echo(render_output(payload, output=output))


@app.command("delete")
def delete_page(
    ctx: typer.Context,
    page_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_page_service(ctx.obj)
    payload = service.delete_raw(page_id) if is_raw_output(output) else service.delete(page_id)
    typer.echo(render_output(payload, output=output))
