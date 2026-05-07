from typer.testing import CliRunner

import atlassian_cli.config.header_substitution as header_substitution
from atlassian_cli.cli import app

runner = CliRunner()


def test_root_help_displays_products() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "jira" in result.stdout
    assert "confluence" in result.stdout
    assert "bitbucket" in result.stdout
    assert "init" in result.stdout
    assert "update" in result.stdout
    assert "--profile" not in result.stdout


def test_root_help_lists_default_alignment_command_groups() -> None:
    result = runner.invoke(app, ["jira", "--help"])

    assert result.exit_code == 0
    assert "field" in result.stdout
    assert "comment" in result.stdout

    result = runner.invoke(app, ["confluence", "--help"])

    assert result.exit_code == 0
    assert "comment" in result.stdout


def test_nested_command_help_does_not_resolve_runtime_config(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "repo-token"

        [bitbucket.headers]
        accessToken = "$(example-oauth token)"
        """.strip()
    )
    commands: list[str] = []
    monkeypatch.setattr(
        header_substitution,
        "run_header_command",
        lambda command: commands.append(command) or "profile-token",
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "bitbucket",
            "pr",
            "get",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert commands == []


def test_nested_command_help_lists_markdown_output_mode() -> None:
    result = runner.invoke(app, ["jira", "issue", "get", "--help"])

    assert result.exit_code == 0
    assert "markdown" in result.stdout
    assert "table" not in result.stdout


def test_cli_rejects_removed_table_output_mode() -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "get",
            "DEMO-1",
            "--output",
            "table",
        ],
    )

    assert result.exit_code != 0
    assert "table" in result.output


def test_pr_list_help_mentions_markdown_output_mode() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--help"])

    assert result.exit_code == 0
    assert "markdown" in result.stdout
    assert "table" not in result.stdout
