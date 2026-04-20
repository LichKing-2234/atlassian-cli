from pathlib import Path

import atlassian_cli.config.header_substitution as header_substitution
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_callback_loads_profile_from_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "alice"
        token = "secret"
        """.strip()
    )

    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda context: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "url": context.url}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--profile",
            "prod_jira",
            "jira",
            "issue",
            "get",
            "OPS-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout


def test_root_callback_reads_top_level_and_profile_headers_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"

        [profiles.prod_bitbucket.headers]
        accessToken = "$(agora-oauth token)"
        """.strip()
    )

    monkeypatch.setattr(
        header_substitution,
        "run_header_command",
        lambda command: "profile-token",
    )

    from atlassian_cli.products.bitbucket.commands import project as project_module

    monkeypatch.setattr(
        project_module,
        "build_project_service",
        lambda context: type(
            "FakeService",
            (),
            {
                "list": lambda self, start, limit: [
                    {
                        "accessToken": context.auth.headers.get("accessToken"),
                        "X-Request-Source": context.auth.headers.get("X-Request-Source"),
                    }
                ]
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--profile",
            "prod_bitbucket",
            "bitbucket",
            "project",
            "list",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"accessToken": "profile-token"' in result.stdout
    assert '"X-Request-Source": "config-default"' in result.stdout


def test_root_callback_flag_headers_override_config_headers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"

        [profiles.prod_bitbucket.headers]
        accessToken = "$(agora-oauth token)"
        """.strip()
    )

    monkeypatch.setattr(
        header_substitution,
        "run_header_command",
        lambda command: "profile-token",
    )

    from atlassian_cli.products.bitbucket.commands import project as project_module

    monkeypatch.setattr(
        project_module,
        "build_project_service",
        lambda context: type(
            "FakeService",
            (),
            {
                "list": lambda self, start, limit: [
                    {"accessToken": context.auth.headers.get("accessToken")}
                ]
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--profile",
            "prod_bitbucket",
            "--header",
            "accessToken: flag-token",
            "bitbucket",
            "project",
            "list",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"accessToken": "flag-token"' in result.stdout


def test_root_callback_does_not_load_default_profile_credentials_when_url_is_explicit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "alice"
        token = "secret"
        """.strip()
    )

    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda context: type(
            "FakeService",
            (),
            {
                "get": lambda self, issue_key: {
                    "key": issue_key,
                    "profile": context.profile,
                    "url": context.url,
                    "username": context.auth.username,
                    "token": context.auth.token,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--url",
            "https://jira.flag.local",
            "jira",
            "issue",
            "get",
            "OPS-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"profile": "inline-jira"' in result.stdout
    assert '"url": "https://jira.flag.local"' in result.stdout
    assert '"username": null' in result.stdout
    assert '"token": null' in result.stdout


def test_root_callback_reports_invalid_header_as_usage_error() -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "--header",
            "Authorization",
            "jira",
            "issue",
            "get",
            "OPS-1",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for --header" in result.output
