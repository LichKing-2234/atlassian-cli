import typer
from click.core import ParameterSource

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.page import PageService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page commands")


def build_page_service(context) -> PageService:
    return PageService(provider=build_provider(context))


def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    values = [item.strip() for item in value.split(",") if item.strip()]
    return values or None


@app.command("get")
def get_page(
    ctx: typer.Context,
    page_id: str | None = typer.Argument(None),
    title: str | None = typer.Option(None, "--title"),
    space_key: str | None = typer.Option(None, "--space-key", "--space"),
    include_metadata: bool = typer.Option(True, "--include-metadata/--no-include-metadata"),
    convert_to_markdown: bool = typer.Option(
        True, "--convert-to-markdown/--no-convert-to-markdown"
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    include_metadata_is_default = (
        ctx.get_parameter_source("include_metadata") is ParameterSource.DEFAULT
    )
    convert_to_markdown_is_default = (
        ctx.get_parameter_source("convert_to_markdown") is ParameterSource.DEFAULT
    )
    use_default_read = (
        include_metadata
        and convert_to_markdown
        and include_metadata_is_default
        and convert_to_markdown_is_default
    )
    if page_id is not None:
        payload = (
            (service.get_raw(page_id) if is_raw_output(output) else service.get(page_id))
            if use_default_read
            else (
                service.get_raw(
                    page_id,
                    include_metadata=include_metadata,
                    convert_to_markdown=convert_to_markdown,
                )
                if is_raw_output(output)
                else service.get(
                    page_id,
                    include_metadata=include_metadata,
                    convert_to_markdown=convert_to_markdown,
                )
            )
        )
    elif title and space_key:
        payload = (
            (
                service.get_by_title_raw(space_key, title)
                if is_raw_output(output)
                else service.get_by_title(space_key, title)
            )
            if use_default_read
            else (
                service.get_by_title_raw(
                    space_key,
                    title,
                    include_metadata=include_metadata,
                    convert_to_markdown=convert_to_markdown,
                )
                if is_raw_output(output)
                else service.get_by_title(
                    space_key,
                    title,
                    include_metadata=include_metadata,
                    convert_to_markdown=convert_to_markdown,
                )
            )
        )
        if payload is None:
            raise typer.BadParameter(f"page not found: {title} in {space_key}")
    else:
        raise typer.BadParameter("provide a page id or both --title and --space")
    typer.echo(render_output(payload, output=output))


@app.command("search")
def search_pages(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    limit: int = typer.Option(25, "--limit"),
    spaces_filter: str | None = typer.Option(None, "--spaces-filter"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.search_raw(query, limit=limit, spaces_filter=_parse_csv(spaces_filter))
        if is_raw_output(output)
        else service.search(query, limit=limit, spaces_filter=_parse_csv(spaces_filter))
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
    convert_to_markdown: bool = typer.Option(
        True, "--convert-to-markdown/--no-convert-to-markdown"
    ),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.history_raw(page_id, version=version, convert_to_markdown=convert_to_markdown)
        if is_raw_output(output)
        else service.history(page_id, version=version, convert_to_markdown=convert_to_markdown)
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
    space_key: str = typer.Option(..., "--space-key", "--space"),
    title: str = typer.Option(..., "--title"),
    content: str = typer.Option(..., "--content", "--body"),
    parent_id: str | None = typer.Option(None, "--parent-id"),
    content_format: str = typer.Option("markdown", "--content-format"),
    enable_heading_anchors: bool = typer.Option(False, "--enable-heading-anchors"),
    include_content: bool = typer.Option(False, "--include-content"),
    emoji: str | None = typer.Option(None, "--emoji"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.create_raw(
            space_key=space_key,
            title=title,
            body=content,
            parent_id=parent_id,
            content_format=content_format,
            enable_heading_anchors=enable_heading_anchors,
            emoji=emoji,
        )
        if is_raw_output(output)
        else service.create(
            space_key=space_key,
            title=title,
            content=content,
            parent_id=parent_id,
            content_format=content_format,
            enable_heading_anchors=enable_heading_anchors,
            include_content=include_content,
            emoji=emoji,
        )
    )
    typer.echo(render_output(payload, output=output))


@app.command("update")
def update_page(
    ctx: typer.Context,
    page_id: str,
    title: str = typer.Option(..., "--title"),
    content: str = typer.Option(..., "--content", "--body"),
    parent_id: str | None = typer.Option(None, "--parent-id"),
    content_format: str = typer.Option("markdown", "--content-format"),
    is_minor_edit: bool = typer.Option(False, "--is-minor-edit"),
    version_comment: str | None = typer.Option(None, "--version-comment"),
    enable_heading_anchors: bool = typer.Option(False, "--enable-heading-anchors"),
    include_content: bool = typer.Option(False, "--include-content"),
    emoji: str | None = typer.Option(None, "--emoji"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    payload = (
        service.update_raw(
            page_id,
            title=title,
            body=content,
            parent_id=parent_id,
            content_format=content_format,
            is_minor_edit=is_minor_edit,
            version_comment=version_comment,
            enable_heading_anchors=enable_heading_anchors,
            emoji=emoji,
        )
        if is_raw_output(output)
        else service.update(
            page_id,
            title=title,
            content=content,
            parent_id=parent_id,
            content_format=content_format,
            is_minor_edit=is_minor_edit,
            version_comment=version_comment,
            enable_heading_anchors=enable_heading_anchors,
            include_content=include_content,
            emoji=emoji,
        )
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
