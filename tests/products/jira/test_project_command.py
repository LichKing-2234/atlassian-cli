from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_project_list_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import project as project_module

    monkeypatch.setattr(
        project_module,
        "build_project_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"list": lambda self: {"results": [{"id": "1", "key": "PROJ", "name": "Demo Project"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "project", "list", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout
