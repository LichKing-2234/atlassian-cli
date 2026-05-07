from pathlib import Path

import pytest

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Deployment, Product, ProductConfig
from atlassian_cli.config.writer import (
    ConfigWriteError,
    product_config_exists,
    write_product_config,
    write_product_configs,
)


def test_write_product_config_creates_new_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"

    write_product_config(
        config_file,
        Product.JIRA,
        ProductConfig(
            deployment=Deployment.SERVER,
            url="https://jira.example.com",
            auth=AuthMode.BASIC,
            username="example-user",
            token="secret",
        ),
    )

    config = load_config(config_file)
    jira = config.product_config(Product.JIRA)
    assert jira is not None
    assert jira.deployment is Deployment.SERVER
    assert jira.url == "https://jira.example.com"
    assert jira.auth is AuthMode.BASIC
    assert jira.username == "example-user"
    assert jira.token == "secret"
    assert config.headers == {}


def test_write_product_config_preserves_headers_and_other_products(tmp_path: Path) -> None:
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

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "old-token"
        """.strip()
    )

    write_product_config(
        config_file,
        Product.CONFLUENCE,
        ProductConfig(
            deployment=Deployment.DC,
            url="https://confluence.example.com",
            auth=AuthMode.PAT,
            token="secret",
        ),
    )

    config = load_config(config_file)
    assert config.headers == {"X-Request-Source": "example-oauth"}
    assert config.product_config(Product.JIRA).url == "https://jira.example.com"
    assert config.product_config(Product.BITBUCKET).url == "https://bitbucket.example.com"
    assert config.product_config(Product.CONFLUENCE).url == "https://confluence.example.com"


def test_write_product_config_refuses_existing_product_without_force(tmp_path: Path) -> None:
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

    with pytest.raises(ConfigWriteError, match=r"\[jira\] already exists"):
        write_product_config(
            config_file,
            Product.JIRA,
            ProductConfig(
                deployment=Deployment.DC,
                url="https://jira-new.example.com",
                auth=AuthMode.PAT,
                token="new-secret",
            ),
        )

    assert config_file.read_text() == original


def test_write_product_config_replaces_existing_product_with_force(tmp_path: Path) -> None:
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

    write_product_config(
        config_file,
        Product.JIRA,
        ProductConfig(
            deployment=Deployment.DC,
            url="https://jira-new.example.com",
            auth=AuthMode.PAT,
            token="new-secret",
        ),
        force=True,
    )

    text = config_file.read_text()
    config = load_config(config_file)
    jira = config.product_config(Product.JIRA)
    assert jira.deployment is Deployment.DC
    assert jira.url == "https://jira-new.example.com"
    assert jira.auth is AuthMode.PAT
    assert jira.username is None
    assert jira.token == "new-secret"
    assert "username" not in text


def test_write_product_configs_writes_multiple_products_in_one_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    write_product_configs(
        config_file,
        {
            Product.JIRA: ProductConfig(
                deployment=Deployment.SERVER,
                url="https://jira.example.com",
                auth=AuthMode.BASIC,
                username="example-user",
                token="secret",
            ),
            Product.BITBUCKET: ProductConfig(
                deployment=Deployment.DC,
                url="https://bitbucket.example.com",
                auth=AuthMode.PAT,
                token="secret",
            ),
        },
    )

    config = load_config(config_file)
    assert config.product_config(Product.JIRA).url == "https://jira.example.com"
    assert config.product_config(Product.BITBUCKET).url == "https://bitbucket.example.com"
    assert config.product_config(Product.CONFLUENCE) is None


def test_product_config_exists_detects_configured_product(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        """.strip()
    )

    assert product_config_exists(config_file, Product.JIRA) is True
    assert product_config_exists(config_file, Product.CONFLUENCE) is False
    assert product_config_exists(tmp_path / "missing.toml", Product.JIRA) is False


def test_product_config_exists_ignores_empty_template_blocks(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]

        [jira.headers]
        """.strip()
    )

    assert product_config_exists(config_file, Product.JIRA) is False
