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
