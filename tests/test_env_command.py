from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_env_command_exports_all_configured_product_values_and_headers(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "${ATLASSIAN_HEADER_SOURCE}"

        [jira]
        deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
        url = "${ATLASSIAN_JIRA_URL}"
        auth = "${ATLASSIAN_JIRA_AUTH}"
        username = "${ATLASSIAN_JIRA_USERNAME}"
        token = "${ATLASSIAN_JIRA_TOKEN}"

        [jira.headers]
        Authorization = "Bearer ${ATLASSIAN_JIRA_BEARER}"
        """.strip()
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "env"],
        env={
            "ATLASSIAN_HEADER_SOURCE": "env-source",
            "ATLASSIAN_JIRA_DEPLOYMENT": "server",
            "ATLASSIAN_JIRA_URL": "https://jira.example.com",
            "ATLASSIAN_JIRA_AUTH": "basic",
            "ATLASSIAN_JIRA_USERNAME": "example-user",
            "ATLASSIAN_JIRA_TOKEN": "secret",
            "ATLASSIAN_JIRA_BEARER": "bearer-token",
        },
    )

    assert result.exit_code == 0
    assert "export ATLASSIAN_JIRA_DEPLOYMENT='server'" in result.stdout
    assert "export ATLASSIAN_JIRA_URL='https://jira.example.com'" in result.stdout
    assert "export ATLASSIAN_JIRA_AUTH='basic'" in result.stdout
    assert "export ATLASSIAN_JIRA_USERNAME='example-user'" in result.stdout
    assert "export ATLASSIAN_JIRA_TOKEN='secret'" in result.stdout
    assert "export ATLASSIAN_HEADER_X_REQUEST_SOURCE='env-source'" in result.stdout
    assert "export ATLASSIAN_JIRA_HEADER_AUTHORIZATION='Bearer bearer-token'" in result.stdout


def test_env_command_shell_quotes_single_quotes(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "${ATLASSIAN_JIRA_USERNAME}"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "env"],
        env={"ATLASSIAN_JIRA_USERNAME": "example'oauth"},
    )

    assert result.exit_code == 0
    assert "export ATLASSIAN_JIRA_USERNAME='example'\"'\"'oauth'" in result.stdout


def test_env_command_fails_without_partial_stdout(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "${MISSING_TEST_JIRA_URL}"
        auth = "basic"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(app, ["--config-file", str(config_file), "env"])

    assert result.exit_code != 0
    assert result.stdout == ""
    plain_output = " ".join(result.output.split())
    assert "Missing environment variable MISSING_TEST_JIRA_URL" in plain_output
    assert "[jira].url" in plain_output


def test_env_command_converts_config_load_errors_to_bad_parameter(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        """.strip()
    )

    result = runner.invoke(app, ["--config-file", str(config_file), "env"])

    assert result.exit_code != 0
    assert result.stdout == ""
    plain_output = " ".join(result.output.split())
    assert "Profile-based config" in plain_output
    assert "[profiles.*]" in plain_output


def test_env_command_normalizes_non_ascii_header_names_to_ascii_safe_exports(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        "X-Äuth-Token" = "secret"
        """.strip()
    )

    result = runner.invoke(app, ["--config-file", str(config_file), "env"])

    assert result.exit_code == 0
    assert "export ATLASSIAN_HEADER_X_UTH_TOKEN='secret'" in result.stdout
    assert "ATLASSIAN_HEADER_X_ÄUTH_TOKEN" not in result.stdout


def test_env_command_fails_on_normalized_header_name_collision_without_partial_stdout(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Foo-Bar = "one"
        X_Foo_Bar = "two"
        """.strip()
    )

    result = runner.invoke(app, ["--config-file", str(config_file), "env"])

    assert result.exit_code != 0
    assert result.stdout == ""
    plain_output = " ".join(result.output.split())
    assert "Duplicate export name" in plain_output
    assert "ATLASSIAN_HEADER_X_FOO_BAR" in plain_output


def test_env_command_rejects_header_names_that_normalize_to_empty_without_partial_stdout(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        "Ä" = "secret"
        """.strip()
    )

    result = runner.invoke(app, ["--config-file", str(config_file), "env"])

    assert result.exit_code != 0
    assert result.stdout == ""
    plain_output = " ".join(result.output.split())
    assert "Header name normalizes to empty export suffix" in plain_output
    assert "Ä" in plain_output
