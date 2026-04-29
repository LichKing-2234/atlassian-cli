from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_field_search_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import field as field_module

    monkeypatch.setattr(
        field_module,
        "build_field_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "search": lambda self, query: {
                    "results": [
                        {"id": "customfield_10001", "name": "Story Points", "type": "number"}
                    ]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "field",
            "search",
            "--query",
            "story",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"name": "Story Points"' in result.stdout


def test_jira_field_options_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import field as field_module

    monkeypatch.setattr(
        field_module,
        "build_field_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "options": lambda self, field_id, project_key, issue_type: {
                    "results": [{"id": "1", "value": "1"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "field",
            "options",
            "customfield_10001",
            "--project",
            "DEMO",
            "--issue-type",
            "Bug",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"value": "1"' in result.stdout
