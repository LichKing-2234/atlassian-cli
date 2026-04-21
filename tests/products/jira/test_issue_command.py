from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_issue_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "summary": "Broken deploy"}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "get", "OPS-1", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"key": "OPS-1"' in result.stdout
