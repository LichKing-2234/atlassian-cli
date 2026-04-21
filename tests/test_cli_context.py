from pathlib import Path

from typer.testing import CliRunner

import atlassian_cli.cli as cli_module
import atlassian_cli.config.header_substitution as header_substitution
from atlassian_cli.cli import app
from atlassian_cli.config.models import LoadedConfig

runner = CliRunner()


def test_root_callback_uses_jira_product_config_without_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
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


def test_root_callback_uses_confluence_product_config_without_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [confluence]
        deployment = "dc"
        url = "https://confluence.example.com"
        auth = "pat"
        token = "wiki-token"
        """.strip()
    )

    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda context: type(
            "FakeService",
            (),
            {"get": lambda self, page_id: {"id": page_id, "url": context.url}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "confluence",
            "page",
            "get",
            "1234",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"url": "https://confluence.example.com"' in result.stdout


def test_root_callback_uses_bitbucket_product_headers_without_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "repo-token"

        [bitbucket.headers]
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
        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "repo-token"

        [bitbucket.headers]
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


def test_root_callback_reports_created_template_for_missing_product_config(
    monkeypatch,
) -> None:
    generated = Path("/tmp/generated-config.toml")
    monkeypatch.setattr(cli_module, "ensure_default_config", lambda path, default_path: True)
    monkeypatch.setattr(cli_module, "load_config", lambda path: LoadedConfig())

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(generated),
            "jira",
            "issue",
            "get",
            "OPS-1",
        ],
    )

    assert result.exit_code == 2
    assert f"Created {generated}. Fill in [jira] or pass" in result.output
    assert "--url" in result.output


def test_root_callback_rejects_removed_profile_flag() -> None:
    result = runner.invoke(app, ["--profile", "prod_jira", "--help"])

    assert result.exit_code == 2
    assert "No such option: --profile" in result.output


def test_root_callback_does_not_load_default_profile_credentials_when_url_is_explicit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.product.local"
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
