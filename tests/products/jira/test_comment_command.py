from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_comment_add_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"add": lambda self, issue_key, body: {"id": "10001", "body": body}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "add",
            "PROJ-1",
            "--body",
            "example approval comment",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "10001"' in result.stdout


def test_jira_comment_edit_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"edit": lambda self, issue_key, comment_id, body: {"id": comment_id, "body": body}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "comment",
            "edit",
            "PROJ-1",
            "10001",
            "--body",
            "updated",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "10001"' in result.stdout
