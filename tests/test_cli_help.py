import re

from typer.testing import CliRunner

import atlassian_cli.config.header_substitution as header_substitution
from atlassian_cli import __version__
from atlassian_cli.cli import app

runner = CliRunner()
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def ci_output_env() -> dict[str, str]:
    return {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "TERM": "xterm-256color",
    }


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", text)


def test_root_help_displays_products_and_local_config_commands() -> None:
    result = runner.invoke(app, ["--help"])
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "jira" in plain_output
    assert "confluence" in plain_output
    assert "bitbucket" in plain_output
    assert "init" in plain_output
    assert "env" in plain_output
    assert "update" in plain_output
    assert "show version and exit" in plain_output.lower()
    assert "--profile" not in plain_output


def test_init_help_explains_product_credentials_and_dynamic_headers() -> None:
    result = runner.invoke(app, ["init", "--help"], terminal_width=160)
    plain_output = " ".join(strip_ansi(result.output).replace("│", " ").lower().split())

    assert result.exit_code == 0
    assert "atlassian product password" in plain_output
    assert "atlassian product api token or pat" in plain_output
    assert "values containing `$()` are stored without executing the command" in plain_output
    assert "command substitution is evaluated only in header values" in plain_output
    assert "`${...}` references remain environment placeholders" in plain_output
    assert "overwrite an existing product section" in plain_output


def test_root_version_outputs_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


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
        Authorization = "Bearer $(example-token-helper)"
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


def test_jira_issue_help_lists_attachment_subcommand() -> None:
    result = runner.invoke(app, ["jira", "issue", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "attachment" in plain_output


def test_confluence_page_help_lists_attachment_subcommand() -> None:
    result = runner.invoke(app, ["confluence", "page", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "attachment" in plain_output


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
    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "--help"],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "markdown" in plain_output
    assert "table" not in plain_output
    assert "--state" in plain_output
    assert "MERGED" in plain_output
    assert "DECLINED" in plain_output
