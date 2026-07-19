from copy import deepcopy

import click
import pytest
from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.commands import pr as pr_module
from atlassian_cli.products.bitbucket.gh_compat.repository_context import GitRepositorySnapshot
from atlassian_cli.products.bitbucket.services.pr_edit import PullRequestEdits

runner = CliRunner()

RAW_PR = {
    "id": 1234,
    "version": 7,
    "title": "Example pull request",
    "description": "example response",
    "fromRef": {
        "id": "refs/heads/feature/DEMO-1234/example-change",
        "displayId": "feature/DEMO-1234/example-change",
        "repository": {"slug": "example-repo", "project": {"key": "DEMO"}},
    },
    "toRef": {
        "id": "refs/heads/main",
        "displayId": "main",
        "repository": {"slug": "example-repo", "project": {"key": "DEMO"}},
    },
    "reviewers": [{"user": {"name": "reviewer-one"}}],
}


def primary_edit_args(selector: str | None, *extra: str) -> list[str]:
    command = [
        "--url",
        "https://bitbucket.example.com",
        "--username",
        "example-user",
        "--password",
        "example response",
        "bitbucket",
        "pr",
        "edit",
    ]
    if selector is not None:
        command.append(selector)
    command.extend(extra)
    return command


def install_edit_fakes(monkeypatch, *, prompt: bool = False):
    calls = {"candidate_lists": [], "loads": [], "edits": [], "providers": 0}

    class FakeProvider:
        def list_pull_requests(self, project_key, repo_slug, state, *, start, limit):
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

    class FakeEditService:
        def __init__(self, actual_provider):
            assert actual_provider is provider

        def load(self, ref):
            calls["loads"].append(ref)
            return deepcopy(RAW_PR)

        def edit(self, ref, edits, *, current=None):
            calls["edits"].append((ref, edits, current))
            return {**deepcopy(RAW_PR), "title": edits.title or RAW_PR["title"]}

    monkeypatch.setattr(pr_module, "build_provider", build_provider)
    monkeypatch.setattr(pr_module, "PullRequestEditService", FakeEditService, raising=False)
    monkeypatch.setattr(pr_module, "can_prompt", lambda *_args, **_kwargs: prompt)
    monkeypatch.setattr(
        pr_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("git called"),
    )
    return calls


def test_edit_help_matches_supported_gh_surface() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "edit", "--help"], color=True)

    assert result.exit_code == 0
    plain_output = click.unstyle(result.stdout)
    assert "[<number> | <url> | <branch>]" in plain_output
    for flag in (
        "--add-reviewer",
        "--base",
        "--body",
        "--body-file",
        "--remove-reviewer",
        "--repo",
        "--title",
    ):
        assert flag in plain_output
    for unsupported in (
        "--add-assignee",
        "--add-label",
        "--add-project",
        "--milestone",
        "--remove-assignee",
        "--remove-label",
        "--remove-milestone",
        "--remove-project",
    ):
        assert unsupported not in plain_output


def test_edit_body_sources_conflict_before_file_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_args: pytest.fail("provider called"))
    monkeypatch.setattr(
        pr_module,
        "read_body_file",
        lambda *_args, **_kwargs: pytest.fail("file read"),
        raising=False,
    )

    result = runner.invoke(
        app,
        primary_edit_args(
            "1234",
            "-R",
            "DEMO/example-repo",
            "--body",
            "example response",
            "--body-file",
            "missing.md",
        ),
    )

    assert result.exit_code == 1
    assert "specify only one of `--body` or `--body-file`" in result.stderr


def test_edit_non_tty_without_flags_fails_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_args: pytest.fail("provider called"))
    monkeypatch.setattr(pr_module, "can_prompt", lambda *_args, **_kwargs: False)

    result = runner.invoke(
        app,
        primary_edit_args("1234", "-R", "DEMO/example-repo"),
    )

    assert result.exit_code == 1
    assert "--title, --body, --base, --add-reviewer, or --remove-reviewer required" in (
        result.stderr
    )


def test_edit_numeric_selector_preserves_explicit_empty_title(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_edit_args(
            "1234",
            "-R",
            "DEMO/example-repo",
            "--title",
            "",
        ),
    )

    assert result.exit_code == 0
    assert result.stdout == (
        "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234\n"
    )
    ref, edits, current = calls["edits"][0]
    assert (ref.repository.slug, ref.number) == ("DEMO/example-repo", 1234)
    assert edits == PullRequestEdits(title="")
    assert current is None
    assert calls["candidate_lists"] == []


def test_edit_url_selector_is_authoritative_over_repo(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch)
    url = (
        "https://bitbucket.example.com/projects/DEMO/repos/example-repo/"
        "pull-requests/1234?example=response#example"
    )

    result = runner.invoke(
        app,
        primary_edit_args(
            url,
            "-R",
            "~example-user/example-repo",
            "--body",
            "example response",
        ),
    )

    assert result.exit_code == 0
    ref = calls["edits"][0][0]
    assert (ref.repository.slug, ref.number) == ("DEMO/example-repo", 1234)
    assert calls["candidate_lists"] == []


def test_edit_branch_selector_uses_finder(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_edit_args(
            "feature/DEMO-1234/example-change",
            "-R",
            "DEMO/example-repo",
            "--base",
            "main",
        ),
    )

    assert result.exit_code == 0
    assert [call[2] for call in calls["candidate_lists"]] == ["OPEN", "DECLINED", "MERGED"]
    assert calls["edits"][0][1].base == "main"


def test_edit_repo_without_selector_uses_current_branch(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch)
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
        primary_edit_args(
            None,
            "-R",
            "DEMO/example-repo",
            "--title",
            "Example pull request",
        ),
    )

    assert result.exit_code == 0
    assert calls["edits"][0][0].number == 1234


def test_edit_reads_body_from_stdin_and_normalizes_reviewers(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_edit_args(
            "1234",
            "-R",
            "DEMO/example-repo",
            "--body-file",
            "-",
            "--add-reviewer",
            "reviewer-one,reviewer-two",
            "--add-reviewer",
            "reviewer-one",
            "--remove-reviewer",
            "reviewer-three,reviewer-four",
        ),
        input="example response\n",
    )

    assert result.exit_code == 0
    edits = calls["edits"][0][1]
    assert edits.body == "example response\n"
    assert edits.add_reviewers == ("reviewer-one", "reviewer-two")
    assert edits.remove_reviewers == ("reviewer-three", "reviewer-four")


def test_edit_tty_without_flags_loads_once_and_prompts(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch, prompt=True)
    prompted = PullRequestEdits(title="Example pull request")
    prompt_calls = []

    def prompt_for_edits(current, **kwargs):
        prompt_calls.append((current, kwargs))
        return prompted

    monkeypatch.setattr(pr_module, "prompt_for_edits", prompt_for_edits, raising=False)

    result = runner.invoke(
        app,
        primary_edit_args("1234", "-R", "DEMO/example-repo"),
        env={"ATLASSIAN_FORCE_TTY": "1"},
    )

    assert result.exit_code == 0
    assert len(calls["loads"]) == 1
    assert calls["edits"][0][1] == prompted
    assert calls["edits"][0][2] == RAW_PR
    assert prompt_calls[0][0] == RAW_PR


def test_edit_prompt_cancellation_exits_two(monkeypatch) -> None:
    calls = install_edit_fakes(monkeypatch, prompt=True)
    prompt_calls = []

    def cancel(*args, **kwargs):
        prompt_calls.append((args, kwargs))
        raise click.Abort()

    monkeypatch.setattr(pr_module, "prompt_for_edits", cancel, raising=False)

    result = runner.invoke(
        app,
        primary_edit_args("1234", "-R", "DEMO/example-repo"),
        env={"ATLASSIAN_FORCE_TTY": "1"},
    )

    assert result.exit_code == 2
    assert len(prompt_calls) == 1
    assert calls["edits"] == []


def test_edit_service_failure_exits_one_without_success_url(monkeypatch) -> None:
    install_edit_fakes(monkeypatch)

    class FailingService:
        def __init__(self, _provider):
            pass

        def edit(self, *_args, **_kwargs):
            raise ValidationError("example response")

    monkeypatch.setattr(pr_module, "PullRequestEditService", FailingService, raising=False)

    result = runner.invoke(
        app,
        primary_edit_args(
            "1234",
            "-R",
            "DEMO/example-repo",
            "--title",
            "Example pull request",
        ),
    )

    assert result.exit_code == 1
    assert "Error: example response" in result.stderr
    assert result.stdout == ""


def test_edit_wrong_host_url_exits_four_before_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_args: pytest.fail("provider called"))

    result = runner.invoke(
        app,
        primary_edit_args(
            "https://example.com/projects/DEMO/repos/example-repo/pull-requests/1234",
            "--title",
            "Example pull request",
        ),
    )

    assert result.exit_code == 4
    assert "repository host does not match" in result.stderr
