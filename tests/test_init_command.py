import re
from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Product

runner = CliRunner()
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", text)


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
    plain_output = strip_ansi(result.output)
    assert "Missing required option for non-interactive init:" in plain_output
    assert "--url" in plain_output
    assert not config_file.exists()


def test_init_basic_missing_credential_mentions_token_and_password(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(config_file),
            "--deployment",
            "server",
            "--url",
            "https://jira.example.com",
            "--auth",
            "basic",
            "--username",
            "example-user",
        ],
    )

    assert result.exit_code != 0
    plain_output = strip_ansi(result.output)
    assert "Missing required option for non-interactive init:" in plain_output
    assert "--token" in plain_output
    assert "--password" in plain_output
    assert not config_file.exists()


def test_init_wizard_later_failure_does_not_write_partial_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "--config-file", str(config_file)],
        input=("y\nserver\nhttps://jira.example.com\nbasic\nexample-user\nsecret\ny\n"),
    )

    assert result.exit_code != 0
    plain_output = strip_ansi(result.output)
    assert "Missing required option for non-interactive init:" in plain_output
    assert "--deployment" in plain_output
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
    assert "[jira] already exists" in strip_ansi(result.output)
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


def test_init_without_product_prompts_for_products_in_order(tmp_path: Path) -> None:
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
            "n\n"
            "y\n"
            "dc\n"
            "https://bitbucket.example.com\n"
            "pat\n"
            "secret\n"
        ),
    )

    assert result.exit_code == 0
    assert result.stdout.index("Configure jira?") < result.stdout.index("Configure confluence?")
    assert result.stdout.index("Configure confluence?") < result.stdout.index(
        "Configure bitbucket?"
    )
    config = load_config(config_file)
    assert config.product_config(Product.JIRA) is not None
    assert config.product_config(Product.CONFLUENCE) is None
    assert config.product_config(Product.BITBUCKET) is not None


def test_init_interactive_existing_product_decline_skips_without_writing(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    original = """
    [jira]
    deployment = "server"
    url = "https://jira.example.com"
    auth = "basic"
    username = "example-user"
    token = "secret"
    """.strip()
    config_file.write_text(original)

    result = runner.invoke(
        app,
        ["init", "jira", "--config-file", str(config_file)],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Skipped [jira]." in result.stdout
    assert config_file.read_text() == original


def test_init_interactive_existing_product_confirm_overwrites(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "example-oauth"

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
        ["init", "jira", "--config-file", str(config_file)],
        input="y\ndc\nhttps://jira-new.example.com\npat\nnew-secret\n",
    )

    assert result.exit_code == 0
    config = load_config(config_file)
    assert config.headers == {"X-Request-Source": "example-oauth"}
    jira = config.product_config(Product.JIRA)
    assert jira.deployment.value == "dc"
    assert jira.url == "https://jira-new.example.com"
    assert jira.auth.value == "pat"
    assert jira.username is None
    assert jira.token == "new-secret"
