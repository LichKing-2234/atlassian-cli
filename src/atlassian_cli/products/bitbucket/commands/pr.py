import os
import sys
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import click
import typer
from typer._click.exceptions import UsageError as TyperUsageError
from typer.core import TyperCommand

from atlassian_cli.auth.models import ResolvedAuth
from atlassian_cli.core.errors import MissingCredentialError
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
from atlassian_cli.products.bitbucket.gh_compat.exit_policy import run_gh_read
from atlassian_cli.products.bitbucket.gh_compat.io import (
    can_prompt,
    color_enabled,
    open_browser,
    page_output,
    stdout_is_tty,
)
from atlassian_cli.products.bitbucket.gh_compat.pr_finder import PullRequestFinder
from atlassian_cli.products.bitbucket.gh_compat.pr_output import (
    MISSING_JSON_VALUE,
    GhPreflightError,
    render_json,
    render_pr_list,
    render_pr_view,
    validate_json_fields,
)
from atlassian_cli.products.bitbucket.gh_compat.repository_context import (
    GitRepositoryContext,
    GitRepositorySnapshot,
    RepositoryResolution,
    RepositoryResolver,
)
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    RepositoryRef,
    ServerIdentity,
    parse_pull_request_url,
    parse_repository_selector,
)
from atlassian_cli.products.bitbucket.services.build_status import BuildStatusService
from atlassian_cli.products.bitbucket.services.pr import PullRequestService
from atlassian_cli.products.bitbucket.services.pr_read import (
    PullRequestListFilters,
    PullRequestReadService,
)
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket pull request commands")
app.add_typer(pr_comment_app, name="comment")

LIST_FIELDS = {"createdAt", "headRefName", "number", "state", "title"}
VIEW_NON_TTY_FIELDS = {
    "additions",
    "author",
    "body",
    "deletions",
    "number",
    "reviewRequests",
    "state",
    "title",
    "url",
}
VIEW_TTY_FIELDS = VIEW_NON_TTY_FIELDS | {
    "baseRefName",
    "comments",
    "commits",
    "createdAt",
    "headRefName",
    "statusCheckRollup",
}
_STATE_MAP = {"open": "OPEN", "closed": "DECLINED", "merged": "MERGED", "all": "ALL"}


def build_pr_service(context) -> PullRequestService:
    return PullRequestService(provider=build_provider(context))


def build_build_status_service(context) -> BuildStatusService:
    return BuildStatusService(provider=build_provider(context))


def require_primary_auth(auth: ResolvedAuth) -> None:
    has_authorization_header = any(
        name.lower() == "authorization" and bool(value) for name, value in auth.headers.items()
    )
    has_basic = bool(auth.username and (auth.password or auth.token))
    if not (auth.token or has_basic or has_authorization_header):
        raise MissingCredentialError("authentication required")


def _normalize_json_argv(args: list[str]) -> list[str]:
    normalized: list[str] = []
    for index, value in enumerate(args):
        normalized.append(value)
        if value == "--json" and (index + 1 == len(args) or args[index + 1].startswith("-")):
            normalized.append(MISSING_JSON_VALUE)
    return normalized


class GhReadCommand(TyperCommand):
    def parse_args(self, ctx, args):
        try:
            return super().parse_args(ctx, _normalize_json_argv(list(args)))
        except (click.UsageError, TyperUsageError) as exc:
            exc.exit_code = 1
            if "unexpected extra argument(s)" in exc.message:
                exc.message = exc.message.replace(
                    "unexpected extra argument(s)", "unexpected extra arguments"
                )
            raise

    def invoke(self, ctx):
        try:
            source = ctx.get_parameter_source("output")
            if source is not None and source.name == "COMMANDLINE":
                typer.echo("DeprecationWarning: The option 'output' is deprecated.", err=True)
            return super().invoke(ctx)
        except (click.UsageError, TyperUsageError) as exc:
            exc.exit_code = 1
            if "unexpected extra argument(s)" in exc.message:
                exc.message = exc.message.replace(
                    "unexpected extra argument(s)", "unexpected extra arguments"
                )
            raise


def resolve_repository(
    server: ServerIdentity,
    *,
    explicit: str | None = None,
    embedded: RepositoryRef | None = None,
) -> RepositoryResolution:
    environment = os.environ
    needs_git = (
        embedded is None and explicit is None and not environment.get("ATLASSIAN_BITBUCKET_REPO")
    )
    snapshot = (
        GitRepositoryContext(Path.cwd()).read()
        if needs_git
        else GitRepositorySnapshot(
            current_branch=None,
            default_remote=None,
            upstream_remote=None,
            remotes={},
        )
    )
    return RepositoryResolver(
        server,
        snapshot,
        env=environment,
        can_prompt=can_prompt(_stdin_is_tty, sys.stdout.isatty, environment),
        choose_remote=lambda names: _choose_remote(names, server, snapshot),
    ).resolve(
        explicit=explicit,
        embedded=embedded,
    )


def _stdin_is_tty() -> bool:
    return sys.stdin.isatty()


def _choose_remote(
    names: list[str],
    server: ServerIdentity,
    snapshot: GitRepositorySnapshot,
) -> str:
    for index, name in enumerate(names, start=1):
        repository = parse_repository_selector(snapshot.remotes[name], server)
        typer.echo(f"{index}. {name} ({repository.slug})", err=True)
    choice = typer.prompt("Choose a repository", type=int, err=True)
    if choice < 1 or choice > len(names):
        raise GhPreflightError("invalid repository selection")
    return names[choice - 1]


def _repository_pull_requests_url(
    server: ServerIdentity,
    repository: RepositoryRef,
    *,
    author: str | None,
    base: str | None,
    head: str | None,
    search: str | None,
    state: str,
) -> str:
    repository_prefix = (
        f"users/{quote(repository.project_key[1:])}"
        if repository.project_key.startswith("~")
        else f"projects/{quote(repository.project_key)}"
    )
    path = (
        f"{server.base_url}/{repository_prefix}/repos/{quote(repository.repo_slug)}/pull-requests"
    )
    parameters = {
        "state": _STATE_MAP[state],
        "author": author,
        "base": base,
        "head": head,
        "search": search,
    }
    query = urlencode({key: value for key, value in parameters.items() if value is not None})
    return f"{path}?{query}" if query else path


def _browser_notice(url: str, *, tty: bool) -> None:
    if not tty:
        return
    parsed = urlsplit(url)
    display_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    typer.echo(f"Opening {display_url} in your browser.", err=True)


def _list_run(
    *,
    ctx: typer.Context,
    author: str | None,
    base: str | None,
    head: str | None,
    json_fields: list[str],
    limit: int,
    repo: str | None,
    search: str | None,
    state: str,
    web: bool,
    output: OutputMode | None,
) -> None:
    fields = validate_json_fields(json_fields, web=web, surface="pr list")
    if output is not None and fields is not None:
        raise GhPreflightError("cannot use `--output` with `--json`")
    if output is not None:
        for option, value in (
            ("--author", author),
            ("--base", base),
            ("--head", head),
            ("--search", search),
            ("--web", web),
        ):
            if value:
                raise GhPreflightError(f"cannot use `{option}` with `--output`")
    if state not in {"open", "closed", "merged", "all"}:
        raise GhPreflightError(f"invalid state: {state}")
    if limit < 1:
        raise GhPreflightError("limit must be greater than zero")

    context = ctx.obj
    require_primary_auth(context.auth)
    server = ServerIdentity.from_url(context.url)
    resolution = resolve_repository(server, explicit=repo)
    repository = resolution.repository

    if output is not None:
        service = build_pr_service(context)
        if is_raw_output(output):
            payload = service.list_raw(
                repository.project_key,
                repository.repo_slug,
                _STATE_MAP[state],
                start=0,
                limit=limit,
            )
        else:
            payload = service.list(
                repository.project_key,
                repository.repo_slug,
                _STATE_MAP[state],
                start=0,
                limit=limit,
            )
        typer.echo(render_output(payload, output=output))
        return

    environment = os.environ
    tty = stdout_is_tty(sys.stdout.isatty, environment)
    if web:
        url = _repository_pull_requests_url(
            server,
            repository,
            author=author,
            base=base,
            head=head,
            search=search,
            state=state,
        )
        _browser_notice(url, tty=tty)
        open_browser(url)
        return

    requested_fields = set(fields) if fields is not None else LIST_FIELDS
    count_total = fields is None and tty
    result = PullRequestReadService(build_provider(context)).list(
        repository,
        PullRequestListFilters(
            state=state,
            limit=limit,
            author=author,
            base=base,
            head=head,
            search=search,
        ),
        requested_fields,
        count_total=count_total,
    )
    color = color_enabled(tty, environment)
    if fields is not None:
        rendered = render_json(result.items, color=color)
    else:
        rendered = render_pr_list(
            result.items,
            repository=repository.slug,
            total=result.total_count,
            filtered=(
                state != "open" or any(value is not None for value in (author, base, head, search))
            ),
            tty=tty,
            color=color,
            now=datetime.now(UTC),
        )
    page_output(
        rendered,
        tty=tty,
        env=environment,
        error_prefix="error starting pager",
    )


@app.command("list", cls=GhReadCommand)
def list_pull_requests(
    ctx: typer.Context,
    author: str | None = typer.Option(None, "--author", "-A"),
    base: str | None = typer.Option(None, "--base", "-B"),
    head: str | None = typer.Option(None, "--head", "-H"),
    json_fields: list[str] = typer.Option([], "--json"),
    limit: int = typer.Option(30, "--limit", "-L"),
    repo: str | None = typer.Option(None, "--repo", "-R"),
    search: str | None = typer.Option(None, "--search", "-S"),
    state: str = typer.Option("open", "--state", "-s"),
    web: bool = typer.Option(False, "--web", "-w"),
    output: OutputMode | None = typer.Option(
        None,
        "--output",
        hidden=True,
    ),
) -> None:
    run_gh_read(
        lambda: _list_run(
            ctx=ctx,
            author=author,
            base=base,
            head=head,
            json_fields=json_fields,
            limit=limit,
            repo=repo,
            search=search,
            state=state,
            web=web,
            output=output,
        )
    )


app.command("ls", cls=GhReadCommand, hidden=True)(list_pull_requests)


def _view_run(
    *,
    ctx: typer.Context,
    selector: str | None,
    comments: bool,
    json_fields: list[str],
    repo: str | None,
    web: bool,
) -> None:
    if repo is not None and selector is None:
        raise GhPreflightError("argument required when using the --repo flag")
    fields = validate_json_fields(json_fields, web=web, surface="pr view")

    context = ctx.obj
    require_primary_auth(context.auth)
    server = ServerIdentity.from_url(context.url)
    embedded = (
        parse_pull_request_url(selector, server).repository
        if selector is not None and "://" in selector
        else None
    )
    resolution = resolve_repository(server, explicit=repo, embedded=embedded)
    provider = build_provider(context)
    ref = PullRequestFinder(provider, server).find(
        selector,
        resolution,
        explicit_repo=repo is not None,
    )

    environment = os.environ
    tty = stdout_is_tty(sys.stdout.isatty, environment)
    if web:
        requested_fields = {"url"}
    elif fields is not None:
        requested_fields = set(fields)
    elif comments and not tty:
        requested_fields = {"comments"}
    elif tty:
        requested_fields = VIEW_TTY_FIELDS
    else:
        requested_fields = VIEW_NON_TTY_FIELDS

    pull_request = PullRequestReadService(provider).get(ref, requested_fields)
    if web:
        url = str(pull_request["url"])
        _browser_notice(url, tty=tty)
        open_browser(url)
        return

    color = color_enabled(tty, environment)
    if fields is not None:
        rendered = render_json(pull_request, color=color)
    else:
        rendered = render_pr_view(
            pull_request,
            repository=ref.repository.slug,
            tty=tty,
            color=color,
            comments=comments,
            now=datetime.now(UTC),
        )
    page_output(
        rendered,
        tty=tty,
        env=environment,
        error_prefix="failed to start pager",
    )


@app.command("view", cls=GhReadCommand)
def view_pull_request(
    ctx: typer.Context,
    selector: str | None = typer.Argument(None, metavar="[<number> | <url> | <branch>]"),
    comments: bool = typer.Option(False, "--comments", "-c"),
    json_fields: list[str] = typer.Option([], "--json"),
    repo: str | None = typer.Option(None, "--repo", "-R"),
    web: bool = typer.Option(False, "--web", "-w"),
) -> None:
    run_gh_read(
        lambda: _view_run(
            ctx=ctx,
            selector=selector,
            comments=comments,
            json_fields=json_fields,
            repo=repo,
            web=web,
        )
    )


@app.command("browse")
def browse_pull_requests(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    state: str = typer.Option(
        "OPEN",
        "--state",
        help="Pull request state to list, for example OPEN, MERGED, or DECLINED.",
    ),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
) -> None:
    service = build_pr_service(ctx.obj)
    if should_use_interactive_output(OutputMode.MARKDOWN, command_kind="collection"):
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
    typer.echo(render_output(payload, output=OutputMode.MARKDOWN))


@app.command("get", hidden=True)
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
    with_lines: bool = typer.Option(False, "--with-lines"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    if with_lines:
        payload = (
            service.diff_with_lines_raw(project_key, repo_slug, pr_id)
            if is_raw_output(output)
            else service.diff_with_lines(project_key, repo_slug, pr_id)
        )
        typer.echo(render_output(payload, output=output))
        return

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


@app.command("build-status", hidden=True)
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


@app.command("approve", hidden=True)
def approve_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    result = (
        service.approve_raw(project_key, repo_slug, pr_id)
        if is_raw_output(output)
        else service.approve(project_key, repo_slug, pr_id)
    )
    typer.echo(render_output(result, output=output))


@app.command("unapprove", hidden=True)
def unapprove_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    result = (
        service.unapprove_raw(project_key, repo_slug, pr_id)
        if is_raw_output(output)
        else service.unapprove(project_key, repo_slug, pr_id)
    )
    typer.echo(render_output(result, output=output))


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
