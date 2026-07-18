import click
import pytest
import typer
from typer._click.exceptions import Abort as TyperAbort
from typer._click.exceptions import BadParameter as TyperBadParameter
from typer.testing import CliRunner

from atlassian_cli.auth.models import AuthMode, ResolvedAuth
from atlassian_cli.cli import app
from atlassian_cli.core.errors import (
    AtlassianCliError,
    MissingCredentialError,
    NotFoundError,
    TransportError,
    ValidationError,
)
from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.bitbucket.commands import pr as pr_module
from atlassian_cli.products.bitbucket.gh_compat.repository_context import GitRepositorySnapshot
from atlassian_cli.products.bitbucket.gh_compat.selectors import RepositoryHostMismatchError
from atlassian_cli.products.bitbucket.services.pr_read import PullRequestListResult

runner = CliRunner()


def _raise(error: BaseException) -> None:
    raise error


@pytest.mark.parametrize(
    "error",
    [
        ValidationError("example response"),
        NotFoundError("example response"),
        TransportError("example response"),
        AtlassianCliError("example response"),
        RuntimeError("example response"),
    ],
)
def test_migrated_read_failures_exit_one(error: Exception, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "_list_run", lambda **_kwargs: _raise(error))

    result = runner.invoke(app, ["bitbucket", "pr", "list"])

    assert result.exit_code == 1
    assert "Error: example response" in result.stderr


@pytest.mark.parametrize(
    "error",
    [
        MissingCredentialError("authentication required"),
        RepositoryHostMismatchError(
            "repository host does not match the configured Bitbucket server"
        ),
    ],
)
def test_migrated_auth_and_host_failures_exit_four(error: Exception, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "_list_run", lambda **_kwargs: _raise(error))

    result = runner.invoke(app, ["bitbucket", "pr", "list"])

    assert result.exit_code == 4
    assert f"Error: {error}" in result.stderr


@pytest.mark.parametrize("error_type", [click.BadParameter, TyperBadParameter])
def test_migrated_bad_parameter_with_missing_auth_cause_exits_four(
    error_type,
    monkeypatch,
) -> None:
    def fail(**_kwargs) -> None:
        try:
            raise MissingCredentialError("authentication required")
        except MissingCredentialError as exc:
            raise error_type("wrapped authentication error") from exc

    monkeypatch.setattr(pr_module, "_list_run", fail)

    result = runner.invoke(app, ["bitbucket", "pr", "list"])

    assert result.exit_code == 4
    assert result.stderr == "Error: authentication required\n"


@pytest.mark.parametrize("error", [KeyboardInterrupt(), click.Abort(), TyperAbort()])
def test_migrated_cancellation_exits_two(error: BaseException, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "_list_run", lambda **_kwargs: _raise(error))

    result = runner.invoke(app, ["bitbucket", "pr", "list"])

    assert result.exit_code == 2


def test_migrated_success_exit_is_not_remapped(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "_list_run", lambda **_kwargs: _raise(typer.Exit(0)))

    result = runner.invoke(app, ["bitbucket", "pr", "list"])

    assert result.exit_code == 0


def test_primary_auth_accepts_token_basic_and_authorization_header() -> None:
    accepted = [
        ResolvedAuth(mode=AuthMode.PAT, token="example response"),
        ResolvedAuth(
            mode=AuthMode.BASIC,
            username="example-user",
            password="example response",
        ),
        ResolvedAuth(
            mode=AuthMode.BASIC,
            headers={"authorization": "Bearer example response"},
        ),
    ]

    for auth in accepted:
        pr_module.require_primary_auth(auth)


def test_primary_auth_rejects_empty_credentials() -> None:
    with pytest.raises(MissingCredentialError, match="authentication required"):
        pr_module.require_primary_auth(ResolvedAuth(mode=AuthMode.BASIC))


def test_primary_missing_pat_uses_gh_auth_exit_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "--auth",
            "pat",
            "bitbucket",
            "pr",
            "list",
            "-R",
            "DEMO/example-repo",
        ],
    )

    assert result.exit_code == 4
    assert "pat authentication requires a token" in result.stderr


def test_hidden_legacy_missing_pat_keeps_usage_exit(monkeypatch) -> None:
    def build_provider(context):
        context.auth
        pytest.fail("provider called")

    monkeypatch.setattr(pr_module, "build_provider", build_provider)

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "--auth",
            "pat",
            "bitbucket",
            "pr",
            "get",
            "DEMO",
            "example-repo",
            "1234",
        ],
    )

    assert result.exit_code == 2
    assert "pat authentication requires a token" in result.stderr


def test_json_missing_value_fails_before_context_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--json"])

    assert result.exit_code == 1
    assert "Specify one or more comma-separated fields" in result.stderr


def test_json_before_option_is_treated_as_missing_value(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--json", "--web"])

    assert result.exit_code == 1
    assert "Specify one or more comma-separated fields" in result.stderr


def test_web_json_conflict_does_not_open_browser_or_resolve_repo(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_module,
        "open_browser",
        lambda *_args, **_kwargs: pytest.fail("browser called"),
        raising=False,
    )
    monkeypatch.setattr(
        pr_module,
        "resolve_repository",
        lambda *_args, **_kwargs: pytest.fail("repo resolved"),
        raising=False,
    )

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "--json", "number", "--web"],
    )

    assert result.exit_code == 1
    assert "cannot use `--web` with `--json`" in result.stderr


def test_json_equals_form_reaches_static_field_validation(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "--json=number,title", "--web"],
    )

    assert result.exit_code == 1
    assert "cannot use `--web` with `--json`" in result.stderr


def test_repeated_json_values_reach_static_field_validation(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "--json", "number", "--json", "unknownField"],
    )

    assert result.exit_code == 1
    assert 'Unknown JSON field: "unknownField"' in result.stderr


def test_invalid_state_fails_before_context_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--state", "invalid"])

    assert result.exit_code == 1
    assert "invalid state" in result.stderr.lower()


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        pytest.param(
            ["--json", "--search", "'bad"],
            "Specify one or more comma-separated fields",
            id="missing-json-value",
        ),
        pytest.param(
            ["--web", "--json", "number", "--search", "draft:true"],
            "cannot use `--web` with `--json`",
            id="web-json-conflict",
        ),
        pytest.param(
            ["--state", "invalid", "--search", "draft:true"],
            "invalid state: invalid",
            id="invalid-state",
        ),
        pytest.param(
            ["--limit", "0", "--search", "draft:true"],
            "limit must be greater than zero",
            id="invalid-limit",
        ),
    ],
)
def test_list_validation_wins_before_invalid_search_or_io(
    arguments: list[str],
    expected_error: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pr_module,
        "require_primary_auth",
        lambda *_args, **_kwargs: pytest.fail("context accessed"),
    )
    monkeypatch.setattr(
        pr_module,
        "resolve_repository",
        lambda *_args, **_kwargs: pytest.fail("repo resolved"),
    )
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    monkeypatch.setattr(
        pr_module,
        "open_browser",
        lambda *_args, **_kwargs: pytest.fail("browser called"),
    )

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", *arguments],
    )

    assert result.exit_code == 1
    assert result.stderr.startswith(expected_error)


@pytest.mark.parametrize(
    "search",
    [
        f"{negated}{qualifier}:DEMO"
        for qualifier in ("assignee", "draft", "label", "milestone", "project", "app", "team")
        for negated in ("", "-")
    ],
)
def test_primary_list_rejects_every_n03_search_qualifier_before_context(
    search: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pr_module,
        "require_primary_auth",
        lambda *_args, **_kwargs: pytest.fail("context accessed"),
    )
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--search", search])

    qualifier = search.lstrip("-").partition(":")[0]
    assert result.exit_code == 1
    assert result.stderr == f"Error: unsupported search qualifier: {qualifier}\n"


@pytest.mark.parametrize(
    ("search", "message"),
    [
        ("in:comments", "unsupported search qualifier: in:comments"),
        ("state:invalid", "unsupported state search value: invalid"),
        ("is:invalid", "unsupported is search value: invalid"),
        ("review:invalid", "unsupported review search value: invalid"),
        ("status:invalid", "unsupported status search value: invalid"),
        ("author:", "search qualifier author requires a value"),
        ("base:", "search qualifier base requires a value"),
        ("head:", "search qualifier head requires a value"),
        ("draft:", "unsupported search qualifier: draft"),
        ("'Example pull request", "No closing quotation"),
    ],
)
def test_primary_list_rejects_invalid_search_syntax_before_context(
    search: str,
    message: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pr_module,
        "require_primary_auth",
        lambda *_args, **_kwargs: pytest.fail("context accessed"),
    )
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--search", search])

    assert result.exit_code == 1
    assert result.stderr == f"Error: {message}\n"


def test_primary_list_web_rejects_search_before_context_or_browser(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_module,
        "require_primary_auth",
        lambda *_args, **_kwargs: pytest.fail("context accessed"),
    )
    monkeypatch.setattr(
        pr_module,
        "resolve_repository",
        lambda *_args, **_kwargs: pytest.fail("repo resolved"),
    )
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    monkeypatch.setattr(
        pr_module,
        "open_browser",
        lambda *_args, **_kwargs: pytest.fail("browser called"),
    )

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "--web", "--search", "draft:true"],
    )

    assert result.exit_code == 1
    assert result.stderr == "Error: unsupported search qualifier: draft\n"


def test_hidden_ls_rejects_search_before_context_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_module,
        "require_primary_auth",
        lambda *_args, **_kwargs: pytest.fail("context accessed"),
    )
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "ls", "--search", "draft:true"],
    )

    assert result.exit_code == 1
    assert result.stderr == "Error: unsupported search qualifier: draft\n"


def test_view_repo_without_selector_fails_before_git_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_: pytest.fail("git called"),
        raising=False,
    )
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "view", "-R", "DEMO/example-repo"],
    )

    assert result.exit_code == 1
    assert "argument required when using the --repo flag" in result.stderr


def test_too_many_view_arguments_use_gh_parser_exit() -> None:
    result = runner.invoke(
        app,
        ["bitbucket", "pr", "view", "1234", "feature/DEMO-1234/example-change"],
    )

    assert result.exit_code == 1
    assert "unexpected extra argument" in result.output.lower()


LIST_PR = {
    "number": 1234,
    "title": "Example pull request",
    "headRefName": "feature/DEMO-1234/example-change",
    "state": "OPEN",
    "createdAt": "2026-07-15T12:00:00Z",
}


def install_read_fakes(
    monkeypatch,
    *,
    tty: bool = False,
    color: bool = False,
    total_count: int = 1,
    items: list[dict] | None = None,
):
    calls: dict[str, object] = {"providers": 0, "lists": [], "pages": []}

    def build_provider(_context):
        calls["providers"] += 1
        return object()

    class FakeReadService:
        def __init__(self, provider):
            calls["provider"] = provider

        def list(self, repository, filters, fields, *, count_total=False):
            calls["lists"].append((repository, filters, fields, count_total))
            selected_items = [LIST_PR] if items is None else items
            projected = [{field: item[field] for field in fields} for item in selected_items]
            return PullRequestListResult(projected, total_count if count_total else None)

    def page_output(text, **kwargs):
        calls["pages"].append((text, kwargs))
        typer.echo(text, nl=False)

    monkeypatch.setattr(pr_module, "build_provider", build_provider)
    monkeypatch.setattr(pr_module, "PullRequestReadService", FakeReadService, raising=False)
    monkeypatch.setattr(pr_module, "stdout_is_tty", lambda *_args, **_kwargs: tty, raising=False)
    monkeypatch.setattr(pr_module, "color_enabled", lambda *_args, **_kwargs: color, raising=False)
    monkeypatch.setattr(pr_module, "page_output", page_output, raising=False)
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("git called"),
        raising=False,
    )
    return calls


def install_legacy_list_fake(monkeypatch):
    calls = []

    class FakeService:
        def list(self, project_key, repo_slug, state, start=0, limit=25):
            calls.append((project_key, repo_slug, state, start, limit))
            return {
                "results": [
                    {
                        "id": 1234,
                        "title": "Example pull request",
                        "description": "example response",
                        "state": state,
                    }
                ],
                "start_at": start,
                "max_results": limit,
            }

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("git called"),
        raising=False,
    )
    return calls


def primary_list_args(*extra: str, include_repo: bool = True) -> list[str]:
    args = [
        "--url",
        "https://bitbucket.example.com",
        "--username",
        "example-user",
        "--password",
        "example response",
        "bitbucket",
        "pr",
        "list",
    ]
    if include_repo:
        args.extend(["-R", "DEMO/example-repo"])
    return [*args, *extra]


def test_primary_list_accepts_project_repo_positionals(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_list_args(
            "DEMO",
            "example-repo",
            "--json",
            "number",
            include_repo=False,
        ),
    )

    assert result.exit_code == 0
    assert calls["lists"][0][0].slug == "DEMO/example-repo"


@pytest.mark.parametrize("positionals", [["DEMO"], ["DEMO", "example-repo", "extra"]])
def test_primary_list_rejects_incomplete_or_extra_positionals(
    positionals: list[str], monkeypatch
) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", *positionals])

    assert result.exit_code == 1


def test_primary_list_rejects_positionals_with_repo_option(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        [
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
            "-R",
            "DEMO/example-repo",
        ],
    )

    assert result.exit_code == 1
    assert "cannot use `PROJECT_KEY REPO_SLUG` with `--repo`" in result.stderr


@pytest.mark.parametrize(
    ("tty", "extra", "expected_stderr"),
    [
        (True, (), "no open pull requests in DEMO/example-repo\n"),
        (
            True,
            ("--search", "Example pull request"),
            "no pull requests match your search in DEMO/example-repo\n",
        ),
        (False, (), ""),
    ],
)
def test_primary_empty_human_list_exits_zero_without_paging(
    tty: bool,
    extra: tuple[str, ...],
    expected_stderr: str,
    monkeypatch,
) -> None:
    calls = install_read_fakes(monkeypatch, tty=tty, total_count=0, items=[])

    result = runner.invoke(app, primary_list_args(*extra))

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == expected_stderr
    assert calls["pages"] == []


def test_primary_empty_json_list_remains_successful_array(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch, tty=True, total_count=0, items=[])

    result = runner.invoke(app, primary_list_args("--json", "number"))

    assert result.exit_code == 0
    assert result.stdout == "[]\n"
    assert result.stderr == ""
    assert len(calls["pages"]) == 1


def test_hidden_legacy_output_selects_v019_renderer_and_warns(monkeypatch) -> None:
    calls = install_legacy_list_fake(monkeypatch)

    result = runner.invoke(app, primary_list_args("--output", "json"))

    assert result.exit_code == 0
    assert calls == [("DEMO", "example-repo", "OPEN", 0, 30)]
    assert '"results"' in result.stdout
    assert result.stderr == "DeprecationWarning: The option 'output' is deprecated.\n"


@pytest.mark.parametrize(
    ("state", "legacy_state"),
    [
        ("OPEN", "OPEN"),
        ("open", "OPEN"),
        ("DECLINED", "DECLINED"),
        ("declined", "DECLINED"),
        ("MERGED", "MERGED"),
        ("merged", "MERGED"),
        ("ALL", "ALL"),
        ("all", "ALL"),
    ],
)
def test_hidden_legacy_output_normalizes_native_states(
    state: str, legacy_state: str, monkeypatch
) -> None:
    calls = install_legacy_list_fake(monkeypatch)

    result = runner.invoke(app, primary_list_args("--state", state, "--output", "json"))

    assert result.exit_code == 0
    assert calls == [("DEMO", "example-repo", legacy_state, 0, 30)]


@pytest.mark.parametrize(
    "extra",
    [
        ("--author", "example-user"),
        ("--base", "main"),
        ("--head", "feature/DEMO-1234/example-change"),
        ("--search", "Example pull request"),
        ("--web",),
    ],
)
def test_hidden_legacy_output_rejects_new_filters_before_provider(extra, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "-R", "DEMO/example-repo", "--output", "json", *extra],
    )

    assert result.exit_code == 1
    assert extra[0] in result.stderr


@pytest.mark.parametrize("option", ["--author", "--base", "--head", "--search"])
def test_hidden_legacy_output_rejects_explicit_empty_filters_before_provider(
    option,
    monkeypatch,
) -> None:
    provider_calls = []

    def build_provider(*args):
        provider_calls.append(args)
        pytest.fail("provider called")

    monkeypatch.setattr(pr_module, "build_provider", build_provider)

    result = runner.invoke(
        app,
        [
            "bitbucket",
            "pr",
            "list",
            "-R",
            "DEMO/example-repo",
            "--output",
            "json",
            f"{option}=",
        ],
    )

    assert result.exit_code == 1
    assert result.stderr == (
        "DeprecationWarning: The option 'output' is deprecated.\n"
        f"cannot use `{option}` with `--output`\n"
    )
    assert provider_calls == []


def test_hidden_legacy_output_rejects_json_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        [
            "bitbucket",
            "pr",
            "list",
            "-R",
            "DEMO/example-repo",
            "--output",
            "json",
            "--json",
            "number",
        ],
    )

    assert result.exit_code == 1
    assert "cannot use `--output` with `--json`" in result.stderr


@pytest.mark.parametrize(
    ("state", "normalized"),
    [
        ("OPEN", "OPEN"),
        ("open", "OPEN"),
        ("DECLINED", "DECLINED"),
        ("declined", "DECLINED"),
        ("MERGED", "MERGED"),
        ("merged", "MERGED"),
        ("ALL", "ALL"),
        ("all", "ALL"),
    ],
)
def test_primary_list_accepts_native_states_case_insensitively(
    state: str, normalized: str, monkeypatch
) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(app, primary_list_args("--state", state, "--json", "number"))

    assert result.exit_code == 0
    assert calls["lists"][0][1].state == normalized


@pytest.mark.parametrize("state", ["closed", "draft", "superseded"])
def test_primary_list_rejects_non_native_states_before_context(state: str, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--state", state])

    assert result.exit_code == 1
    assert f"invalid state: {state}" in result.stderr


def test_primary_list_forwards_all_supported_filters(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_list_args(
            "--author",
            "example-user",
            "--base",
            "main",
            "--head",
            "feature/DEMO-1234/example-change",
            "--search",
            '"Example pull request" in:title',
            "--state",
            "merged",
            "--limit",
            "17",
            "--json",
            "number,title",
        ),
    )

    assert result.exit_code == 0
    filters = calls["lists"][0][1]
    assert (
        filters.author,
        filters.base,
        filters.head,
        filters.search,
        filters.state,
        filters.limit,
    ) == (
        "example-user",
        "main",
        "feature/DEMO-1234/example-change",
        '"Example pull request" in:title',
        "MERGED",
        17,
    )


@pytest.mark.parametrize(
    ("option", "attribute"),
    [
        ("--author", "author"),
        ("--base", "base"),
        ("--head", "head"),
        ("--search", "search"),
    ],
)
def test_primary_list_preserves_explicit_empty_filters(option, attribute, monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_list_args(f"{option}=", "--json", "number"),
    )

    assert result.exit_code == 0
    assert getattr(calls["lists"][0][1], attribute) == ""


def test_primary_list_rejects_zero_limit_before_context_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, ["bitbucket", "pr", "list", "--limit", "0"])

    assert result.exit_code == 1
    assert "limit must be greater than zero" in result.stderr


def test_primary_list_json_is_compact_and_requests_exact_fields(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(app, primary_list_args("--json", "number,title"))

    assert result.exit_code == 0
    assert result.stdout == '[{"number":1234,"title":"Example pull request"}]\n'
    assert calls["lists"][0][2] == {"number", "title"}
    assert calls["lists"][0][3] is False


@pytest.mark.parametrize(
    "json_args",
    [
        ("--json=number,title",),
        ("--json", "number", "--json", "title"),
    ],
)
def test_primary_list_accepts_equals_and_repeated_json_options(json_args, monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(app, primary_list_args(*json_args))

    assert result.exit_code == 0
    assert result.stdout == '[{"number":1234,"title":"Example pull request"}]\n'
    assert calls["lists"][0][2] == {"number", "title"}


def test_hidden_ls_alias_invokes_primary_list(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)
    args = primary_list_args("--json", "number")
    args[args.index("list")] = "ls"

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert result.stdout == '[{"number":1234}]\n'
    assert len(calls["lists"]) == 1


def test_primary_list_uses_line_presenter_and_pager_by_default(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(app, primary_list_args())

    assert result.exit_code == 0
    assert result.stdout.startswith("1234\tExample pull request\t")
    assert calls["lists"][0][2] == pr_module.LIST_FIELDS
    assert calls["lists"][0][3] is False
    assert calls["pages"][0][1]["error_prefix"] == "error starting pager"


def test_primary_list_tty_counts_total_for_human_output(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch, tty=True, total_count=7)

    result = runner.invoke(app, primary_list_args())

    assert result.exit_code == 0
    assert "Showing 1 of 7 open pull requests" in result.stdout
    assert calls["lists"][0][3] is True
    assert calls["pages"][0][1]["tty"] is True


def test_primary_list_injects_detected_terminal_width(monkeypatch) -> None:
    install_read_fakes(monkeypatch, tty=True)
    captured = {}
    monkeypatch.setattr(pr_module, "terminal_width", lambda: 47, raising=False)

    def render_pr_list(*_args, **kwargs):
        captured["width"] = kwargs["width"]
        return "example response\n"

    monkeypatch.setattr(pr_module, "render_pr_list", render_pr_list)

    result = runner.invoke(app, primary_list_args())

    assert result.exit_code == 0
    assert captured["width"] == 47


def test_primary_list_tty_json_uses_color_and_pager_without_counting(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch, tty=True, color=True)

    result = runner.invoke(app, primary_list_args("--json", "number"), color=True)

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout
    assert calls["lists"][0][3] is False
    assert calls["pages"][0][1]["tty"] is True


def test_root_output_does_not_select_hidden_legacy_renderer(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)
    args = primary_list_args()
    args[0:0] = ["--output", "json"]

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert result.stdout.startswith("1234\tExample pull request\t")
    assert "DeprecationWarning" not in result.stderr
    assert len(calls["lists"]) == 1


def test_primary_list_uses_environment_repo_without_git(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)
    args = primary_list_args("--json", "number")
    repo_index = args.index("-R")
    del args[repo_index : repo_index + 2]

    result = runner.invoke(app, args, env={"ATLASSIAN_BITBUCKET_REPO": "DEMO/example-repo"})

    assert result.exit_code == 0
    assert calls["lists"][0][0].slug == "DEMO/example-repo"


def test_primary_list_foreign_host_exits_four_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    args = primary_list_args("--json", "number")
    args[args.index("DEMO/example-repo")] = "jira.example.com/DEMO/example-repo"

    result = runner.invoke(app, args)

    assert result.exit_code == 4
    assert "repository host does not match" in result.stderr


def test_primary_list_web_opens_without_listing_or_provider(monkeypatch) -> None:
    urls = []
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    monkeypatch.setattr(pr_module, "open_browser", urls.append, raising=False)
    monkeypatch.setattr(pr_module, "stdout_is_tty", lambda *_args, **_kwargs: False, raising=False)
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("git called"),
        raising=False,
    )

    result = runner.invoke(
        app,
        primary_list_args(
            "--state",
            "merged",
            "--base",
            "main",
            "--search",
            "Example pull request",
            "--web",
        ),
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert len(urls) == 1
    assert urls[0].startswith(
        "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests?"
    )
    assert "state=MERGED" in urls[0]
    assert "base=main" in urls[0]
    assert "search=Example+pull+request" in urls[0]


def test_primary_list_web_tty_notice_drops_query_from_display(monkeypatch) -> None:
    urls = []
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    monkeypatch.setattr(pr_module, "open_browser", urls.append, raising=False)
    monkeypatch.setattr(pr_module, "stdout_is_tty", lambda *_args, **_kwargs: True, raising=False)
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("git called"),
        raising=False,
    )

    result = runner.invoke(app, primary_list_args("--web"))

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == (
        "Opening https://bitbucket.example.com/projects/DEMO/repos/example-repo/"
        "pull-requests in your browser.\n"
    )
    assert urls[0].endswith("?state=OPEN")


VIEW_PR = {
    "additions": 1,
    "author": {"login": "example-user", "name": "Example Author"},
    "baseRefName": "main",
    "body": "example response",
    "comments": [
        {
            "author": {"login": "reviewer-one", "name": "reviewer-one"},
            "authorAssociation": "NONE",
            "body": "example comment",
            "createdAt": "2026-07-15T12:00:00Z",
            "updatedAt": "2026-07-15T12:00:00Z",
            "url": "https://bitbucket.example.com/example-comment",
        }
    ],
    "commits": [{"oid": "example response"}],
    "createdAt": "2026-07-15T12:00:00Z",
    "deletions": 0,
    "headRefName": "feature/DEMO-1234/example-change",
    "number": 1234,
    "reviewRequests": [{"login": "reviewer-one", "name": "reviewer-one"}],
    "_reviewers": [
        {
            "user": {"login": "reviewer-one", "name": "reviewer-one"},
            "status": "UNAPPROVED",
        }
    ],
    "state": "OPEN",
    "statusCheckRollup": [],
    "title": "Example pull request",
    "url": ("https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"),
}


def install_view_fakes(monkeypatch, *, tty: bool = False, color: bool = False):
    calls: dict[str, object] = {
        "candidate_lists": [],
        "gets": [],
        "pages": [],
        "providers": 0,
    }

    class FakeProvider:
        def list_pull_requests(self, project_key, repo_slug, state, start=0, limit=100):
            calls["candidate_lists"].append((project_key, repo_slug, state, start, limit))
            if state != "OPEN":
                return []
            return [
                {
                    "id": 1234,
                    "state": "OPEN",
                    "createdDate": 1,
                    "fromRef": {
                        "displayId": "feature/DEMO-1234/example-change",
                        "repository": {
                            "slug": repo_slug,
                            "project": {"key": project_key},
                        },
                    },
                }
            ]

    provider = FakeProvider()

    def build_provider(_context):
        calls["providers"] += 1
        return provider

    class FakeReadService:
        def __init__(self, actual_provider):
            assert actual_provider is provider

        def get(self, ref, fields):
            calls["gets"].append((ref, fields))
            return {field: VIEW_PR[field] for field in fields}

    def page_output(text, **kwargs):
        calls["pages"].append((text, kwargs))
        typer.echo(text, nl=False)

    monkeypatch.setattr(pr_module, "build_provider", build_provider)
    monkeypatch.setattr(pr_module, "PullRequestReadService", FakeReadService, raising=False)
    monkeypatch.setattr(pr_module, "stdout_is_tty", lambda *_args, **_kwargs: tty, raising=False)
    monkeypatch.setattr(pr_module, "color_enabled", lambda *_args, **_kwargs: color, raising=False)
    monkeypatch.setattr(pr_module, "page_output", page_output, raising=False)
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("git called"),
        raising=False,
    )
    return calls


def primary_view_args(selector: str | None, *extra: str) -> list[str]:
    command = [
        "--url",
        "https://bitbucket.example.com",
        "--username",
        "example-user",
        "--password",
        "example response",
        "bitbucket",
        "pr",
        "view",
    ]
    if selector is not None:
        command.append(selector)
    command.extend(extra)
    return command


def test_primary_view_numeric_selector_uses_explicit_repo_without_git(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args("1234", "-R", "DEMO/example-repo", "--json", "number,title"),
    )

    assert result.exit_code == 0
    assert result.stdout == '{"number":1234,"title":"Example pull request"}\n'
    assert calls["candidate_lists"] == []
    ref, fields = calls["gets"][0]
    assert (ref.repository.slug, ref.number, fields) == (
        "DEMO/example-repo",
        1234,
        {"number", "title"},
    )


def test_primary_view_pr_url_is_authoritative_over_repo_and_avoids_git(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)
    url = (
        "https://bitbucket.example.com/projects/DEMO/repos/example-repo/"
        "pull-requests/1234?example=response#example"
    )

    result = runner.invoke(
        app,
        primary_view_args(url, "-R", "~example-user/example-repo", "--json", "number"),
    )

    assert result.exit_code == 0
    ref = calls["gets"][0][0]
    assert (ref.repository.slug, ref.number) == ("DEMO/example-repo", 1234)
    assert calls["candidate_lists"] == []


def test_primary_view_branch_selector_uses_finder(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args(
            "feature/DEMO-1234/example-change",
            "-R",
            "DEMO/example-repo",
            "--json",
            "number",
        ),
    )

    assert result.exit_code == 0
    assert [call[2] for call in calls["candidate_lists"]] == ["OPEN", "DECLINED", "MERGED"]
    assert calls["gets"][0][0].number == 1234


def test_primary_view_omitted_selector_uses_current_branch(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)
    snapshot = GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={
            "origin": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
        },
    )
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: type("FakeGit", (), {"read": lambda self: snapshot})(),
    )

    result = runner.invoke(app, primary_view_args(None, "--json", "number"))

    assert result.exit_code == 0
    assert calls["gets"][0][0].number == 1234
    assert calls["gets"][0][0].repository.slug == "DEMO/example-repo"


def test_primary_view_environment_repo_with_omitted_selector_uses_current_branch(
    monkeypatch,
) -> None:
    calls = install_view_fakes(monkeypatch)
    snapshot = GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={},
    )
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: type("FakeGit", (), {"read": lambda self: snapshot})(),
    )

    result = runner.invoke(
        app,
        primary_view_args(None, "--json", "number"),
        env={"ATLASSIAN_BITBUCKET_REPO": "DEMO/example-repo"},
    )

    assert result.exit_code == 0
    assert calls["gets"][0][0].number == 1234
    assert calls["gets"][0][0].repository.slug == "DEMO/example-repo"


def test_primary_view_comments_non_tty_outputs_only_comments(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args("1234", "-R", "DEMO/example-repo", "--comments"),
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("author:\treviewer-one\n")
    assert "title:\tExample pull request" not in result.stdout
    assert calls["gets"][0][1] == {"comments"}
    assert calls["pages"][0][1]["error_prefix"] == "failed to start pager"


def test_primary_view_json_takes_precedence_over_comments(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args(
            "1234",
            "-R",
            "DEMO/example-repo",
            "--comments",
            "--json",
            "number",
        ),
    )

    assert result.exit_code == 0
    assert result.stdout == '{"number":1234}\n'
    assert calls["gets"][0][1] == {"number"}


def test_primary_view_human_uses_presenter_fields_and_view_pager_prefix(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args("1234", "-R", "DEMO/example-repo"),
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("title:\tExample pull request\n")
    assert calls["gets"][0][1] == pr_module.VIEW_NON_TTY_FIELDS
    assert "_reviewers" in calls["gets"][0][1]
    assert "reviewRequests" not in calls["gets"][0][1]
    assert calls["pages"][0][1]["error_prefix"] == "failed to start pager"


def test_primary_view_injects_detected_terminal_width(monkeypatch) -> None:
    install_view_fakes(monkeypatch, tty=True)
    captured = {}
    monkeypatch.setattr(pr_module, "terminal_width", lambda: 53, raising=False)

    def render_pr_view(*_args, **kwargs):
        captured["width"] = kwargs["width"]
        return "example response\n"

    monkeypatch.setattr(pr_module, "render_pr_view", render_pr_view)

    result = runner.invoke(
        app,
        primary_view_args("1234", "-R", "DEMO/example-repo"),
    )

    assert result.exit_code == 0
    assert captured["width"] == 53


def test_primary_view_tty_json_uses_color_and_pager(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch, tty=True, color=True)

    result = runner.invoke(
        app,
        primary_view_args("1234", "-R", "DEMO/example-repo", "--json", "number"),
        color=True,
    )

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout
    assert calls["pages"][0][1]["tty"] is True


def test_primary_view_web_requests_only_url_and_opens_full_url(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch, tty=True)
    urls = []
    monkeypatch.setattr(pr_module, "open_browser", urls.append, raising=False)
    full_url = VIEW_PR["url"] + "?example=response#example"
    monkeypatch.setitem(VIEW_PR, "url", full_url)

    result = runner.invoke(
        app,
        primary_view_args("1234", "-R", "DEMO/example-repo", "--web"),
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == (
        "Opening https://bitbucket.example.com/projects/DEMO/repos/example-repo/"
        "pull-requests/1234 in your browser.\n"
    )
    assert calls["gets"][0][1] == {"url"}
    assert calls["pages"] == []
    assert urls == [full_url]


def ambiguous_snapshot() -> GitRepositorySnapshot:
    return GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={
            "reviewer-one": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "reviewer-two": ("https://bitbucket.example.com/scm/~example-user/example-repo.git"),
        },
    )


def install_ambiguous_git(monkeypatch) -> None:
    snapshot = ambiguous_snapshot()
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: type("FakeGit", (), {"read": lambda self: snapshot})(),
    )
    monkeypatch.setattr(pr_module, "_stdin_is_tty", lambda: True, raising=False)


def test_primary_view_tty_chooser_selects_numbered_remote(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)
    install_ambiguous_git(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args(None, "--json", "number"),
        input="1\n",
        env={"ATLASSIAN_FORCE_TTY": "1"},
    )

    assert result.exit_code == 0
    assert "reviewer-one (DEMO/example-repo)" in result.stderr
    assert "reviewer-two (~example-user/example-repo)" in result.stderr
    assert calls["gets"][0][0].repository.slug == "DEMO/example-repo"


def test_primary_view_prompt_disabled_keeps_exact_ambiguity_error(monkeypatch) -> None:
    install_view_fakes(monkeypatch)
    install_ambiguous_git(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args(None, "--json", "number"),
        env={
            "ATLASSIAN_FORCE_TTY": "1",
            "ATLASSIAN_PROMPT_DISABLED": "",
        },
    )

    assert result.exit_code == 1
    assert "multiple Bitbucket remotes match: reviewer-one, reviewer-two; use -R" in result.stderr


def test_primary_view_ignores_gh_prompt_disabled(monkeypatch) -> None:
    calls = install_view_fakes(monkeypatch)
    install_ambiguous_git(monkeypatch)

    result = runner.invoke(
        app,
        primary_view_args(None, "--json", "number"),
        input="2\n",
        env={"ATLASSIAN_FORCE_TTY": "1", "GH_PROMPT_DISABLED": "1"},
    )

    assert result.exit_code == 0
    assert calls["gets"][0][0].repository.slug == "~example-user/example-repo"


def test_primary_view_chooser_cancel_exits_two(monkeypatch) -> None:
    install_view_fakes(monkeypatch)
    install_ambiguous_git(monkeypatch)
    monkeypatch.setattr(pr_module, "_choose_remote", lambda *_args: _raise(TyperAbort()))

    result = runner.invoke(
        app,
        primary_view_args(None, "--json", "number"),
        env={"ATLASSIAN_FORCE_TTY": "1"},
    )

    assert result.exit_code == 2


def test_bitbucket_pr_browse_markdown_non_tty_uses_summary_payload(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ]
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "browse",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert "Example pull request" in result.stdout
    assert "Long body" not in result.stdout


def test_pr_browse_uses_existing_full_screen_browser_in_tty(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module, "browse_collection", lambda source: calls.setdefault("source", source)
    )
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [{"id": 42, "title": "Example pull request"}],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: (
                    CollectionPage(
                        items=[{"id": 42, "title": "Example pull request"}],
                        start=start,
                        limit=limit,
                        total=1,
                    )
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "browse",
            "DEMO",
            "example-repo",
            "--state",
            "OPEN",
            "--start",
            "0",
            "--limit",
            "25",
        ],
    )

    assert result.exit_code == 0
    assert calls["source"].title == "Bitbucket pull requests"


def test_bitbucket_pr_browse_interactive_source_uses_compact_preview_renderers(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    sample_item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "Example Author"},
        "title": "[FEAT] DEMO-1234 example preview change",
        "reviewers": [
            {"display_name": "reviewer-one"},
            {"display_name": "reviewer-two"},
            {"display_name": "reviewer-three"},
            {"display_name": "reviewer-four"},
        ],
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2026-04-27T13:19:55+00:00",
        "description": "Line one\nLine two\nLine three\nLine four",
        "diff": "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n",
    }
    captured: dict[str, str] = {}

    class FakeService:
        def list_page(self, project_key, repo_slug, state, start, limit):
            return CollectionPage(items=[sample_item], start=start, limit=limit, total=1)

        def get(self, project_key, repo_slug, pr_id):
            return sample_item

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "browse_collection",
        lambda source: captured.update(
            {
                "item": source.render_item(1, sample_item),
                "preview": source.render_preview(sample_item),
                "detail": source.render_detail(sample_item),
            }
        ),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "browse",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert (
        captured["item"] == "24990  OPEN  Example Author  [FEAT] DEMO-1234 example preview change"
    )
    assert "Reviewers: reviewer-one, reviewer-two, reviewer-three, +1 more" in captured["preview"]
    assert captured["detail"].startswith("# 24990 - [FEAT] DEMO-1234 example preview change")
    assert "\x1b[" in captured["detail"]


def test_bitbucket_pr_browse_interactive_source_fetches_detail_with_diff(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls: dict[str, object] = {}
    captured: dict[str, object] = {}

    class FakeService:
        def list_page(self, project_key, repo_slug, state, start, limit):
            return CollectionPage(
                items=[{"id": 42, "title": "Example pull request"}], start=0, limit=25, total=1
            )

        def get_detail(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"id": pr_id, "title": "Example pull request", "diff": "+example change\n"}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "browse_collection",
        lambda source: captured.setdefault("detail", source.fetch_detail({"id": 42})),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "browse",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert captured["detail"]["diff"] == "+example change\n"


def test_bitbucket_pr_diff_outputs_markdown_diff_detail(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get_detail": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                    "state": "OPEN",
                    "diff": "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n",
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("# 42 - Example pull request")
    assert "## Diff" in result.stdout
    assert "+example change" in result.stdout
    assert "\x1b[" not in result.stdout


def test_bitbucket_pr_diff_outputs_colored_diff_for_tty(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_color_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get_detail": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                    "state": "OPEN",
                    "diff": "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n",
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
        ],
        color=True,
    )

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout
    assert "+example change" in result.stdout


def test_bitbucket_pr_diff_with_lines_outputs_structured_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def diff_with_lines(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {
                "id": pr_id,
                "files": [
                    {
                        "path": "example.py",
                        "hunks": [
                            {
                                "lines": [
                                    {
                                        "type": "ADDED",
                                        "new_line": 1,
                                        "text": "+example response",
                                        "anchor": {
                                            "path": "example.py",
                                            "line": 1,
                                            "line_type": "ADDED",
                                        },
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
            "--with-lines",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"line_type": "ADDED"' in result.stdout


def test_bitbucket_pr_diff_with_lines_raw_output_uses_raw_service(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def diff_with_lines_raw(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"values": [{"destination": {"toString": "example.py"}}]}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
            "--with-lines",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"values"' in result.stdout


def test_bitbucket_pr_approve_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def approve(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"approved": True, "status": "APPROVED"}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "approve",
            "DEMO",
            "example-repo",
            "42",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"approved": true' in result.stdout


def test_bitbucket_pr_unapprove_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def unapprove(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"approved": False, "status": "UNAPPROVED"}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "unapprove",
            "DEMO",
            "example-repo",
            "42",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"approved": false' in result.stdout


def test_bitbucket_pr_approve_raw_output_uses_raw_service(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def approve_raw(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"approved": True, "status": "APPROVED", "raw": {"id": 42}}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "approve",
            "DEMO",
            "example-repo",
            "42",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"raw": {' in result.stdout


def test_pr_browse_falls_back_to_markdown_when_interactive_import_fails(
    monkeypatch,
) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module, "browse_collection", lambda source: (_ for _ in ()).throw(ImportError("boom"))
    )
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: (
                    CollectionPage(
                        items=[{"id": 42, "title": "Example pull request"}],
                        start=start,
                        limit=limit,
                        total=1,
                    )
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "browse",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert "Example pull request" in result.stdout


def test_pr_browse_falls_back_to_markdown_when_interactive_runtime_fails(
    monkeypatch,
) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module, "browse_collection", lambda source: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start=0, limit=25: {
                    "results": [
                        {
                            "id": 42,
                            "title": "Example pull request",
                            "description": "Long body",
                            "state": "OPEN",
                        }
                    ],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: (
                    CollectionPage(
                        items=[{"id": 42, "title": "Example pull request"}],
                        start=start,
                        limit=limit,
                        total=1,
                    )
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {
                    "id": pr_id,
                    "title": "Example pull request",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "browse",
            "DEMO",
            "example-repo",
        ],
    )

    assert result.exit_code == 0
    assert "Example pull request" in result.stdout
