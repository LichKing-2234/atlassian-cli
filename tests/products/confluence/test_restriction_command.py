from click import unstyle
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_page_restriction_help_is_read_only() -> None:
    group = runner.invoke(app, ["confluence", "page", "restriction", "--help"])
    command = runner.invoke(app, ["confluence", "page", "restriction", "get", "--help"])

    assert group.exit_code == 0
    assert command.exit_code == 0
    group_output = unstyle(group.output)
    command_output = " ".join(unstyle(command.output).replace("│", " ").split())
    assert "get" in group_output
    assert "set" not in group_output
    assert "Read page view and edit restrictions without changing access." in command_output
    assert "Confluence page ID." in command_output


def test_confluence_page_restriction_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page_restriction as restriction_module

    monkeypatch.setattr(
        restriction_module,
        "build_restriction_service",
        lambda *_args: type(
            "FakeService",
            (),
            {
                "get": lambda self, page_id: {
                    "read": {"users": ["~example-user"], "groups": ["reviewer-one"]},
                    "update": {"users": [], "groups": []},
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "restriction",
            "get",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"read"' in result.stdout
    assert '"update"' in result.stdout
    assert '"reviewer-one"' in result.stdout
