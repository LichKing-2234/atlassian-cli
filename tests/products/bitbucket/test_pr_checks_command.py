from copy import deepcopy

import pytest
import typer
from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.products.bitbucket.commands import pr as pr_module
from atlassian_cli.products.bitbucket.gh_compat.repository_context import GitRepositorySnapshot

runner = CliRunner()

CHECK_PR = {
    "headRefName": "feature/DEMO-1234/example-change",
    "headRefOid": "abc123",
    "url": "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234",
}


def _args(selector: str | None = "1234", *extra: str) -> list[str]:
    values = [
        "--url",
        "https://bitbucket.example.com",
        "--username",
        "example-user",
        "--password",
        "example response",
        "bitbucket",
        "pr",
        "checks",
    ]
    if selector is not None:
        values.append(selector)
    values.extend(extra)
    return values


def _build(state: str) -> dict:
    return {
        "key": "DEMO-1234",
        "name": "Example pull request",
        "state": state,
        "url": "https://bitbucket.example.com/example-response",
        "description": "example response",
    }


def _snapshot() -> GitRepositorySnapshot:
    return GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={"origin": "https://bitbucket.example.com/scm/DEMO/example-repo.git"},
    )


def install_checks_fakes(
    monkeypatch,
    *,
    statuses: list[list[dict]] | None = None,
    pull_requests: list[dict] | None = None,
    tty: bool = False,
):
    statuses = statuses or [[_build("SUCCESSFUL")]]
    pull_requests = pull_requests or [deepcopy(CHECK_PR)]
    calls = {"lists": [], "reads": [], "commits": [], "pages": [], "sleeps": []}

    class FakeProvider:
        def list_pull_requests(self, project_key, repo_slug, state, start=0, limit=100):
            calls["lists"].append((project_key, repo_slug, state, start, limit))
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
    state_index = {"value": 0}

    class FakeReadService:
        def __init__(self, actual_provider):
            assert actual_provider is provider

        def get(self, ref, fields):
            index = min(state_index["value"], len(pull_requests) - 1)
            value = pull_requests[index]
            calls["reads"].append((ref, fields))
            return {field: value.get(field) for field in fields}

    class FakeBuildStatusService:
        def __init__(self, actual_provider):
            assert actual_provider is provider

        def for_commit(self, commit):
            index = min(state_index["value"], len(statuses) - 1)
            state_index["value"] += 1
            calls["commits"].append(commit)
            results = statuses[index]
            return {"commit": commit, "overall_state": "UNKNOWN", "results": results}

    def page_output(text, **kwargs):
        calls["pages"].append((text, kwargs))
        typer.echo(text, nl=False)

    monkeypatch.setattr(pr_module, "build_provider", lambda _context: provider)
    monkeypatch.setattr(pr_module, "PullRequestReadService", FakeReadService, raising=False)
    monkeypatch.setattr(pr_module, "BuildStatusService", FakeBuildStatusService, raising=False)
    monkeypatch.setattr(pr_module, "stdout_is_tty", lambda *_args, **_kwargs: tty)
    monkeypatch.setattr(pr_module, "color_enabled", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(pr_module, "terminal_width", lambda: 120)
    monkeypatch.setattr(pr_module, "page_output", page_output)
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: type("FakeGit", (), {"read": lambda self: _snapshot()})(),
    )
    monkeypatch.setattr(
        pr_module.time,
        "sleep",
        lambda seconds: calls["sleeps"].append(seconds),
    )
    return calls


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (("--fail-fast",), "cannot use `--fail-fast` flag without `--watch` flag"),
        (("--interval", "5"), "cannot use `--interval` flag without `--watch` flag"),
        (("--watch", "--json", "name"), "cannot use `--watch` with `--json` flag"),
        (("--web", "--json", "name"), "cannot use `--web` with `--json`"),
    ],
)
def test_checks_static_conflicts_fail_before_provider(
    options: tuple[str, ...],
    message: str,
    monkeypatch,
) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, _args("1234", *options))

    assert result.exit_code == 1
    assert message in result.stderr


def test_checks_repo_without_selector_fails_before_git_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_: pytest.fail("git called"),
    )

    result = runner.invoke(app, _args(None, "-R", "DEMO/example-repo"))

    assert result.exit_code == 1
    assert "argument required when using the --repo flag" in result.stderr


def test_checks_missing_json_value_lists_check_fields_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, _args("1234", "--json"))

    assert result.exit_code == 1
    assert "Specify one or more comma-separated fields" in result.stderr
    assert "  bucket\n" in result.stderr
    assert "  workflow\n" in result.stderr
    assert "  number\n" not in result.stderr


def test_checks_unknown_json_field_lists_check_fields_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(app, _args("1234", "--json", "number"))

    assert result.exit_code == 1
    assert 'Unknown JSON field: "number"' in result.stderr
    assert "  name\n" in result.stderr


@pytest.mark.parametrize(
    ("state", "exit_code", "status"),
    [
        ("SUCCESSFUL", 0, "pass"),
        ("FAILED", 1, "fail"),
        ("INPROGRESS", 8, "pending"),
    ],
)
def test_checks_human_output_uses_head_commit_and_gh_exit_codes(
    state: str,
    exit_code: int,
    status: str,
    monkeypatch,
) -> None:
    calls = install_checks_fakes(monkeypatch, statuses=[[_build(state)]])

    result = runner.invoke(app, _args("1234", "-R", "DEMO/example-repo"))

    assert result.exit_code == exit_code
    assert f"Example pull request\t{status}\t0\t" in result.stdout
    assert calls["commits"] == ["abc123"]
    assert calls["reads"][0][1] == {"headRefName", "headRefOid"}
    assert calls["pages"][0][1]["error_prefix"] == "failed to start pager"


def test_checks_json_projects_fields_and_exits_zero_for_failures(monkeypatch) -> None:
    calls = install_checks_fakes(monkeypatch, statuses=[[_build("FAILED")]], tty=True)

    result = runner.invoke(
        app,
        _args(
            "1234",
            "-R",
            "DEMO/example-repo",
            "--json",
            "name,state,bucket,link",
        ),
    )

    assert result.exit_code == 0
    assert result.stdout == (
        '[{"bucket":"fail","link":"https://bitbucket.example.com/example-response",'
        '"name":"Example pull request","state":"FAILURE"}]\n'
    )
    assert calls["commits"] == ["abc123"]
    assert calls["pages"] == []


@pytest.mark.parametrize("interval", ["9223372037", "-9223372037"])
def test_checks_rejects_interval_duration_overflow_before_provider(interval, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--watch", "--interval", interval),
    )

    assert result.exit_code == 1
    assert (
        f'could not parse `--interval` flag: time: invalid duration "{interval}s"' in result.stderr
    )


@pytest.mark.parametrize(
    ("selector", "extra"),
    [
        ("1234", ("-R", "DEMO/example-repo")),
        (
            "https://bitbucket.example.com/projects/DEMO/repos/example-repo/"
            "pull-requests/1234?example=response#example",
            ("-R", "~example-user/example-repo"),
        ),
        ("feature/DEMO-1234/example-change", ("-R", "DEMO/example-repo")),
        (None, ()),
    ],
)
def test_checks_reuses_pr_selection_rules(selector, extra, monkeypatch) -> None:
    calls = install_checks_fakes(monkeypatch)

    result = runner.invoke(app, _args(selector, *extra, "--json", "name"))

    assert result.exit_code == 0
    assert calls["reads"][0][0].number == 1234
    assert calls["reads"][0][0].repository.slug == "DEMO/example-repo"


def test_checks_errors_when_pr_has_no_head_commit(monkeypatch) -> None:
    calls = install_checks_fakes(
        monkeypatch,
        pull_requests=[{**CHECK_PR, "headRefOid": None}],
    )

    result = runner.invoke(app, _args("1234", "-R", "DEMO/example-repo"))

    assert result.exit_code == 1
    assert "no commit found on the pull request" in result.stderr
    assert calls["commits"] == []


def test_checks_errors_when_head_has_no_checks(monkeypatch) -> None:
    install_checks_fakes(monkeypatch, statuses=[[]])

    result = runner.invoke(app, _args("1234", "-R", "DEMO/example-repo"))

    assert result.exit_code == 1
    assert "no checks reported on the 'feature/DEMO-1234/example-change' branch" in result.stderr


def test_checks_web_opens_pr_without_fetching_build_statuses(monkeypatch) -> None:
    calls = install_checks_fakes(monkeypatch, tty=True)
    urls = []
    monkeypatch.setattr(pr_module, "open_browser", urls.append)

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--web"),
    )

    assert result.exit_code == 0
    assert calls["reads"][0][1] == {"url"}
    assert calls["commits"] == []
    assert urls == [CHECK_PR["url"]]
    assert "Opening https://bitbucket.example.com/" in result.stderr


def test_checks_watch_follows_new_head_until_checks_pass(monkeypatch) -> None:
    calls = install_checks_fakes(
        monkeypatch,
        tty=True,
        statuses=[[_build("INPROGRESS")], [_build("SUCCESSFUL")]],
        pull_requests=[
            {**CHECK_PR, "headRefOid": "abc123"},
            {**CHECK_PR, "headRefOid": "def456"},
        ],
    )

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--watch", "--interval", "5"),
        color=True,
    )

    assert result.exit_code == 0
    assert calls["commits"] == ["abc123", "def456"]
    assert calls["sleeps"] == [5]
    assert "\x1b[?1049h" in result.stdout
    assert "Refreshing checks status every 5 seconds" in result.stdout
    assert "\x1b[?1049l" in result.stdout
    assert result.stdout.count("All checks were successful") >= 1


def test_checks_watch_negative_interval_matches_go_immediate_sleep(monkeypatch) -> None:
    calls = install_checks_fakes(
        monkeypatch,
        statuses=[[_build("INPROGRESS")], [_build("SUCCESSFUL")]],
    )

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--watch", "--interval", "-1"),
    )

    assert result.exit_code == 0
    assert calls["commits"] == ["abc123", "abc123"]
    assert calls["sleeps"] == [0]


def test_checks_watch_fail_fast_stops_on_first_failure(monkeypatch) -> None:
    calls = install_checks_fakes(
        monkeypatch,
        statuses=[[_build("FAILED"), _build("INPROGRESS")], [_build("SUCCESSFUL")]],
    )

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--watch", "--fail-fast"),
    )

    assert result.exit_code == 1
    assert calls["commits"] == ["abc123"]
    assert calls["sleeps"] == []


def test_checks_watch_restores_tty_on_cancellation(monkeypatch) -> None:
    calls = install_checks_fakes(
        monkeypatch,
        tty=True,
        statuses=[[_build("INPROGRESS")]],
    )

    def cancel(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(pr_module.time, "sleep", cancel)

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--watch"),
        color=True,
    )

    assert result.exit_code == 2
    assert calls["commits"] == ["abc123"]
    assert "\x1b[?1049h" in result.stdout
    assert "\x1b[?1049l" in result.stdout


def test_checks_watch_restores_tty_when_screen_entry_is_interrupted(monkeypatch) -> None:
    calls = install_checks_fakes(
        monkeypatch,
        tty=True,
        statuses=[[_build("INPROGRESS")]],
    )
    writes = []
    original_echo = typer.echo

    def interrupt_entry(message="", **kwargs):
        writes.append(message)
        if message == "\x1b[?1049h":
            raise KeyboardInterrupt
        return original_echo(message, **kwargs)

    monkeypatch.setattr(pr_module.typer, "echo", interrupt_entry)

    result = runner.invoke(
        app,
        _args("1234", "-R", "DEMO/example-repo", "--watch"),
        color=True,
    )

    assert result.exit_code == 2
    assert calls["commits"] == []
    assert writes[:2] == ["\x1b[?1049h", "\x1b[?1049l"]
