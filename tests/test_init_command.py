from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Product

runner = CliRunner()


def test_init_single_product_interactive_writes_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "jira", "--config-file", str(config_file)],
        input="server\nhttps://jira.example.com\nbasic\nexample-user\nsecret\n",
    )

    assert result.exit_code == 0
    assert f"Wrote [jira] to {config_file}" in result.stdout
    config = load_config(config_file)
    jira = config.product_config(Product.JIRA)
    assert jira.deployment.value == "server"
    assert jira.url == "https://jira.example.com"
    assert jira.auth.value == "basic"
    assert jira.username == "example-user"
    assert jira.token == "secret"


def test_init_single_product_non_interactive_writes_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "init",
            "bitbucket",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
            "--url",
            "https://bitbucket.example.com",
            "--auth",
            "pat",
            "--token",
            "secret",
        ],
    )

    assert result.exit_code == 0
    config = load_config(config_file)
    bitbucket = config.product_config(Product.BITBUCKET)
    assert bitbucket.deployment.value == "dc"
    assert bitbucket.url == "https://bitbucket.example.com"
    assert bitbucket.auth.value == "pat"
    assert bitbucket.token == "secret"


def test_init_non_interactive_missing_required_values_fails_without_writing(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "init",
            "confluence",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
        ],
    )

    assert result.exit_code != 0
    assert "Missing required option for non-interactive init: --url" in result.output
    assert not config_file.exists()


def test_init_wizard_later_failure_does_not_write_partial_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "--config-file", str(config_file)],
        input=(
            "y\n"
            "server\n"
            "https://jira.example.com\n"
            "basic\n"
            "example-user\n"
            "secret\n"
            "y\n"
        ),
    )

    assert result.exit_code != 0
    assert "Missing required option for non-interactive init:" in result.output
    assert "--deployment" in result.output
    assert not config_file.exists()


def test_init_rejects_existing_product_without_force_in_non_interactive_mode(
    tmp_path: Path,
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

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
            "--url",
            "https://jira-new.example.com",
            "--auth",
            "pat",
            "--token",
            "new-secret",
        ],
    )

    assert result.exit_code != 0
    assert "[jira] already exists" in result.output
    assert "https://jira-new.example.com" not in config_file.read_text()


def test_init_force_replaces_existing_product_in_non_interactive_mode(tmp_path: Path) -> None:
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

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
            "--url",
            "https://jira-new.example.com",
            "--auth",
            "pat",
            "--token",
            "new-secret",
            "--force",
        ],
    )

    assert result.exit_code == 0
    jira = load_config(config_file).product_config(Product.JIRA)
    assert jira.deployment.value == "dc"
    assert jira.url == "https://jira-new.example.com"
    assert jira.auth.value == "pat"
    assert jira.username is None
    assert jira.token == "new-secret"
