import re

import pytest
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


def test_jira_issue_help_lists_reparent_subtask_subcommand() -> None:
    result = runner.invoke(app, ["jira", "issue", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "reparent-subtask" in plain_output


def test_jira_update_assignment_and_transition_help_lists_aligned_inputs() -> None:
    issue_help = strip_ansi(runner.invoke(app, ["jira", "issue", "--help"]).output)
    update_help = strip_ansi(runner.invoke(app, ["jira", "issue", "update", "--help"]).output)
    assign_help = strip_ansi(runner.invoke(app, ["jira", "issue", "assign", "--help"]).output)
    transition_help = strip_ansi(
        runner.invoke(app, ["jira", "issue", "transition", "--help"]).output
    )

    assert "assign" in issue_help
    for option in (
        "--fields",
        "--additional-fields",
        "--components",
        "--attachments",
        "--transition",
        "--comment",
        "--comment-visibility",
        "--worklog",
        "--worklog-started",
    ):
        assert option in update_help
    assert "--assignee" in assign_help
    for option in ("--transition-id", "--to", "--fields", "--comment"):
        assert option in transition_help


def test_jira_discovery_help_lists_aligned_inputs() -> None:
    user_help = strip_ansi(runner.invoke(app, ["jira", "user", "search", "--help"]).output)
    field_help = strip_ansi(runner.invoke(app, ["jira", "field", "search", "--help"]).output)
    options_help = strip_ansi(runner.invoke(app, ["jira", "field", "options", "--help"]).output)

    for option in ("--query", "--project-key", "--issue-key", "--limit"):
        assert option in user_help
    for option in ("--keyword", "--query", "--limit"):
        assert option in field_help
    for option in (
        "--project-key",
        "--project",
        "--issue-type",
        "--contains",
        "--return-limit",
    ):
        assert option in options_help


def test_jira_issue_create_help_documents_semantic_inputs_and_markup_escape() -> None:
    result = runner.invoke(
        app,
        ["jira", "issue", "create", "--help"],
        env=ci_output_env(),
        terminal_width=180,
    )
    plain_output = " ".join(strip_ansi(result.output).replace("│", " ").split())

    assert result.exit_code == 0
    for option in (
        "--project-key",
        "--summary",
        "--issue-type",
        "--assignee",
        "--description",
        "--components",
        "--additional-fields",
    ):
        assert option in plain_output
    assert "Markdown" in plain_output
    assert "Jira wiki markup" in plain_output
    assert "markdown" in plain_output
    assert "jira" in plain_output


def test_jira_issue_batch_create_help_documents_semantic_validation() -> None:
    result = runner.invoke(
        app,
        ["jira", "issue", "batch-create", "--help"],
        env=ci_output_env(),
        terminal_width=180,
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    for field in ("project_key", "summary", "issue_type", "description", "assignee", "components"):
        assert field in plain_output
    assert "--validate-only" in plain_output
    assert "without creating" in plain_output


def test_jira_issue_link_help_keeps_direction_explicit() -> None:
    issue_help = runner.invoke(app, ["jira", "issue", "--help"], env=ci_output_env())
    create_help = runner.invoke(
        app,
        ["jira", "issue", "link", "create", "--help"],
        env=ci_output_env(),
        terminal_width=160,
    )
    types_help = runner.invoke(
        app,
        ["jira", "issue", "link", "types", "--help"],
        env=ci_output_env(),
        terminal_width=160,
    )
    plain_output = strip_ansi(create_help.output)

    assert issue_help.exit_code == create_help.exit_code == types_help.exit_code == 0
    assert "link" in strip_ansi(issue_help.output)
    assert "--inward" in plain_output
    assert "inwardIssue" in plain_output
    assert "--outward" in plain_output
    assert "outwardIssue" in plain_output
    assert "--comment-visibility" in plain_output
    assert "--name-filter" in strip_ansi(types_help.output)


def test_jira_comment_help_documents_core_visibility_and_body_formats() -> None:
    for command in ("add", "edit"):
        result = runner.invoke(
            app,
            ["jira", "comment", command, "--help"],
            env=ci_output_env(),
            terminal_width=160,
        )
        plain_output = strip_ansi(result.output)

        assert result.exit_code == 0
        for option in ("--body", "--visibility", "--body-format"):
            assert option in plain_output
        assert "markdown" in plain_output
        assert "jira" in plain_output
        assert "role|group" in plain_output
        assert "--public" not in plain_output
        assert "--private" not in plain_output


def test_confluence_page_help_lists_attachment_subcommand() -> None:
    result = runner.invoke(app, ["confluence", "page", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "attachment" in plain_output


def test_confluence_page_read_help_lists_fixed_version_navigation_inputs() -> None:
    get_help = strip_ansi(runner.invoke(app, ["confluence", "page", "get", "--help"]).output)
    children_help = strip_ansi(
        runner.invoke(app, ["confluence", "page", "children", "--help"]).output
    )
    tree_help = strip_ansi(runner.invoke(app, ["confluence", "page", "tree", "--help"]).output)

    assert "full page URL" in get_help
    assert "tiny link" in get_help
    for option in ("--expand", "--limit", "--start"):
        assert option in children_help
    assert "--limit" in tree_help


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


def test_pr_list_help_matches_first_slice() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "[PROJECT_KEY]" in output
    assert "[REPO_SLUG]" in output
    for option in (
        "--author",
        "--base",
        "--head",
        "--json",
        "--limit",
        "--repo",
        "--search",
        "--state",
        "--web",
    ):
        assert option in output
    for state in ("OPEN", "DECLINED", "MERGED", "ALL"):
        assert state in output
    assert "closed" not in output
    for absent in (
        "--app",
        "--assignee",
        "--draft",
        "--label",
        "--jq",
        "--template",
        "--output",
    ):
        assert absent not in output


def test_pr_browse_help_preserves_only_legacy_browser_arguments() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "browse", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    for value in ("PROJECT_KEY", "REPO_SLUG", "--state", "--start", "--limit"):
        assert value in output
    for absent in ("--author", "--json", "--repo", "--search", "--web", "--output"):
        assert absent not in output


def test_pr_view_help_matches_first_slice() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "view", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    for value in ("[<number> | <url> | <branch>]", "--comments", "--json", "--repo", "--web"):
        assert value in output
    for absent in ("--jq", "--output", "--template"):
        assert absent not in output


def test_pr_checks_help_matches_gh_core_surface() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "checks", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    for value in (
        "[<number> | <url> | <branch>]",
        "--fail-fast",
        "--interval",
        "--json",
        "--repo",
        "--watch",
        "--web",
    ):
        assert value in output
    for absent in ("--jq", "--output", "--required", "--template"):
        assert absent not in output


def test_pr_help_hides_callable_legacy_commands() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    for visible in ("browse", "checks", "comment", "create", "diff", "list", "merge", "view"):
        assert visible in output
    for hidden in ("get", "build-status", "approve", "unapprove", "ls"):
        assert hidden not in output


def test_bitbucket_api_help_matches_supported_gh_rest_surface() -> None:
    result = runner.invoke(app, ["bitbucket", "api", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "<endpoint>" in output
    for option in (
        "--field",
        "--header",
        "--include",
        "--input",
        "--jq",
        "--method",
        "--paginate",
        "--raw-field",
        "--silent",
        "--slurp",
        "--verbose",
    ):
        assert option in output
    for absent in ("--cache", "--hostname", "--output", "--preview", "--template"):
        assert absent not in output


@pytest.mark.parametrize("command", ["get", "build-status", "approve", "unapprove"])
def test_hidden_legacy_pr_commands_remain_callable(command: str) -> None:
    result = runner.invoke(app, ["bitbucket", "pr", command, "--help"], env=ci_output_env())

    assert result.exit_code == 0
    assert "Usage:" in strip_ansi(result.output)
