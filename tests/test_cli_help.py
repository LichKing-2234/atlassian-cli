from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_help_displays_products() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "jira" in result.stdout
    assert "confluence" in result.stdout
    assert "bitbucket" in result.stdout
    assert "--profile" not in result.stdout
