from pathlib import Path

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


def test_root_callback_reads_header_flag_and_env(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"
        """.strip()
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
            "--header",
            "accessToken: flag-token",
            "bitbucket",
            "project",
            "list",
            "--output",
            "json",
        ],
        env={"ATLASSIAN_HEADER": "X-Request-Source: agora-oauth"},
    )

    assert result.exit_code == 0
    assert '"accessToken": "flag-token"' in result.stdout
    assert '"X-Request-Source": "agora-oauth"' in result.stdout
