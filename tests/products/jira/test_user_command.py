import pytest
from click import unstyle
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_user_search_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import user as user_module

    calls = {}

    def search(_self, query, *, project_key, issue_key, limit):
        calls["args"] = (query, project_key, issue_key, limit)
        return {"results": [{"display_name": "Example Author", "name": "example-user"}]}

    monkeypatch.setattr(
        user_module,
        "build_user_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"search": search},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "user",
            "search",
            "--query",
            "example",
            "--project-key",
            "DEMO",
            "--limit",
            "12",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout
    assert calls["args"] == ("example", "DEMO", None, 12)


def test_jira_user_search_maps_project_and_issue_scopes(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import user as user_module

    calls = []

    class FakeService:
        def search(self, query, *, project_key, issue_key, limit):
            calls.append((query, project_key, issue_key, limit))
            return {"results": []}

    monkeypatch.setattr(user_module, "build_user_service", lambda *_args: FakeService())

    project_result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "user",
            "search",
            "--query",
            "Example Author",
            "--project-key",
            "DEMO",
            "--limit",
            "12",
            "--output",
            "json",
        ],
    )
    issue_result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "user",
            "search",
            "--query",
            "Example Collaborator",
            "--issue-key",
            "DEMO-1",
            "--limit",
            "7",
            "--output",
            "json",
        ],
    )

    assert project_result.exit_code == 0
    assert issue_result.exit_code == 0
    assert calls == [
        ("Example Author", "DEMO", None, 12),
        ("Example Collaborator", None, "DEMO-1", 7),
    ]


@pytest.mark.parametrize(
    "scope_args",
    [[], ["--project-key", "DEMO", "--issue-key", "DEMO-1"]],
)
def test_jira_user_search_requires_exactly_one_assignable_scope(scope_args) -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "user",
            "search",
            "--query",
            "example",
            *scope_args,
        ],
    )

    assert result.exit_code == 2
    output = unstyle(result.output)
    assert "pass exactly one of" in output
    assert "--project-key" in output
    assert "--issue-key" in output
