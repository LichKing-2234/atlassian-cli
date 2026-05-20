import re
from pathlib import Path

from typer.testing import CliRunner

import atlassian_cli.cli as cli_module
import atlassian_cli.config.header_substitution as header_substitution
from atlassian_cli.cli import app
from atlassian_cli.core.errors import ConfigError

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
        username = "example-user"
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
            "DEMO-1",
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
        Authorization = "Bearer $(example-token-helper)"
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
                        "authorization": context.auth.headers.get("Authorization"),
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
    assert '"authorization": "Bearer profile-token"' in result.stdout
    assert '"X-Request-Source": "config-default"' in result.stdout


def test_root_callback_resolves_env_backed_product_fields_before_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "${ATLASSIAN_DEPLOYMENT}"
        url = "https://${ATLASSIAN_HOST}"
        auth = "${ATLASSIAN_AUTH}"
        username = "${ATLASSIAN_USERNAME}"
        token = "${ATLASSIAN_TOKEN}"
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
            "jira",
            "issue",
            "get",
            "DEMO-1",
            "--output",
            "json",
        ],
        env={
            **ci_output_env(),
            "ATLASSIAN_DEPLOYMENT": "server",
            "ATLASSIAN_HOST": "jira.example.com",
            "ATLASSIAN_AUTH": "basic",
            "ATLASSIAN_USERNAME": "example-user",
            "ATLASSIAN_TOKEN": "example-token",
        },
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout
    assert '"username": "example-user"' in result.stdout
    assert '"token": "example-token"' in result.stdout


def test_root_callback_only_resolves_active_product_block(
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
        username = "${ATLASSIAN_USERNAME}"
        token = "secret"

        [confluence]
        deployment = "${MISSING_CONFLUENCE_DEPLOYMENT}"
        url = "https://confluence.example.com"
        auth = "pat"
        token = "wiki-token"
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
                    "url": context.url,
                    "username": context.auth.username,
                }
            },
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
            "DEMO-1",
            "--output",
            "json",
        ],
        env={
            **ci_output_env(),
            "ATLASSIAN_USERNAME": "example-user",
        },
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout
    assert '"username": "example-user"' in result.stdout


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
        Authorization = "Bearer $(example-token-helper)"
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
                    {"authorization": context.auth.headers.get("Authorization")}
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
            "Authorization: Bearer flag-token",
            "bitbucket",
            "project",
            "list",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"authorization": "Bearer flag-token"' in result.stdout


def test_root_callback_explicit_url_still_uses_top_level_headers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "${ATLASSIAN_SOURCE}"

        [jira]
        deployment = "server"
        url = "https://jira.product.local"
        auth = "basic"
        username = "example-user"
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
                    "request_source": context.auth.headers.get("X-Request-Source"),
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
            "DEMO-1",
            "--output",
            "json",
        ],
        env={
            **ci_output_env(),
            "ATLASSIAN_SOURCE": "config-default",
        },
    )

    assert result.exit_code == 0
    assert '"profile": "inline-jira"' in result.stdout
    assert '"url": "https://jira.flag.local"' in result.stdout
    assert '"request_source": "config-default"' in result.stdout


def test_root_callback_reports_created_template_for_missing_product_config(
    monkeypatch,
) -> None:
    generated = Path("/tmp/generated-config.toml")
    monkeypatch.setattr(cli_module, "ensure_default_config", lambda path, default_path: True)
    monkeypatch.setattr(cli_module, "load_raw_config_data", lambda path: {})

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(generated),
            "jira",
            "issue",
            "get",
            "DEMO-1",
        ],
        env={"CI": "true", "GITHUB_ACTIONS": "true", "TERM": "xterm-256color"},
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Created" in plain_output
    assert generated.name in plain_output
    assert "[jira]" in plain_output
    assert "--url." in plain_output
    assert "--url" in plain_output


def test_root_callback_reports_created_template_for_empty_generated_product_block(
    tmp_path: Path,
    monkeypatch,
) -> None:
    generated = tmp_path / "config.toml"
    monkeypatch.setattr(cli_module, "DEFAULT_CONFIG_FILE", generated)

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(generated),
            "jira",
            "issue",
            "get",
            "DEMO-1",
        ],
        env={"CI": "true", "GITHUB_ACTIONS": "true", "TERM": "xterm-256color"},
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Created" in plain_output
    assert generated.name in plain_output
    assert "[jira]" in plain_output
    assert "--url." in plain_output


def test_root_callback_rejects_removed_profile_flag() -> None:
    result = runner.invoke(app, ["--profile", "prod_jira", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "--profile" in plain_output


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
        username = "example-user"
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
            "DEMO-1",
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
            "DEMO-1",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value for --header" in plain_output


def test_root_callback_reports_missing_pat_token_as_usage_error() -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "--auth",
            "pat",
            "bitbucket",
            "pr",
            "list",
            "EXAMPLE",
            "example-repo",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "pat authentication requires a token" in plain_output.lower()


def test_root_callback_reports_invalid_interpolated_product_enum_as_usage_error(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "${ATLASSIAN_DEPLOYMENT}"
        url = "https://${ATLASSIAN_HOST}"
        auth = "${ATLASSIAN_AUTH}"
        username = "${ATLASSIAN_USERNAME}"
        token = "${ATLASSIAN_TOKEN}"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "jira",
            "issue",
            "get",
            "DEMO-1",
        ],
        env={
            **ci_output_env(),
            "ATLASSIAN_DEPLOYMENT": "invalid",
            "ATLASSIAN_HOST": "jira.example.com",
            "ATLASSIAN_AUTH": "basic",
            "ATLASSIAN_USERNAME": "example-user",
            "ATLASSIAN_TOKEN": "example-token",
        },
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value for --config-file" in plain_output
    assert "Invalid config.toml configuration" in plain_output
    assert "[jira].deployment" in plain_output
    assert "server" in plain_output


def test_root_callback_reports_removed_profiles_config_as_usage_error(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.demo]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "example-token"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "jira",
            "issue",
            "get",
            "DEMO-1",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value for --config-file" in plain_output
    assert "Profile-based config [profiles.*]" in plain_output
    assert "removed." in plain_output


def test_root_callback_reports_config_runtime_auth_failure_as_usage_error(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value for --config-file" in plain_output
    assert "pat authentication requires a token" in plain_output.lower()


def test_root_callback_reports_explicit_url_header_failure_as_config_file_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        Authorization = "$(example-token-helper)"
        """.strip()
    )

    monkeypatch.setattr(
        header_substitution,
        "run_header_command",
        lambda command: (_ for _ in ()).throw(
            ConfigError("Header command failed with exit code 1: example-token-helper")
        ),
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
            "DEMO-1",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value for --config-file" in plain_output
    assert "Header command failed with exit code 1" in plain_output


def test_root_callback_reports_explicit_url_auth_failure_as_generic_error_with_headers_present(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--url",
            "https://bitbucket.flag.local",
            "--auth",
            "pat",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value:" in plain_output
    assert "Invalid value for --config-file" not in plain_output
    assert "pat authentication requires a token" in plain_output.lower()


def test_root_callback_reports_non_url_auth_override_failure_as_generic_error(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "basic"
        username = "example-user"
        password = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--auth",
            "pat",
            "bitbucket",
            "pr",
            "list",
            "DEMO",
            "example-repo",
        ],
        env=ci_output_env(),
    )
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 2
    assert "Invalid value:" in plain_output
    assert "Invalid value for --config-file" not in plain_output
    assert "pat authentication requires a token" in plain_output.lower()
