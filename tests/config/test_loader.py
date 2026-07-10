from pathlib import Path

import pytest

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_config, load_raw_config_data
from atlassian_cli.config.models import Product, ProductConfig
from atlassian_cli.core.errors import ConfigError


def test_load_config_reads_top_level_headers(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"
        """.strip()
    )

    config = load_config(config_file)

    assert config.headers == {
        "X-Request-Source": "config-default",
    }


def test_load_config_reads_top_level_product_sections(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"

        [jira.headers]
        Authorization = "Bearer $(example-token-helper)"

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"
        """.strip()
    )

    config = load_config(config_file)

    assert config.headers == {"X-Request-Source": "config-default"}
    assert config.product_config(Product.JIRA).url == "https://jira.example.com"
    assert config.product_config(Product.JIRA).headers == {
        "Authorization": "Bearer $(example-token-helper)",
    }
    assert config.product_config(Product.BITBUCKET).auth is AuthMode.PAT


def test_product_config_to_profile_config_requires_deployment_url_and_auth() -> None:
    product_config = ProductConfig(url="https://jira.example.com")

    with pytest.raises(ConfigError, match="missing required fields"):
        product_config.to_profile_config(product=Product.JIRA, name="jira")


def test_load_config_rejects_non_string_header_values(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        Authorization = 42
        """.strip()
    )

    with pytest.raises(ConfigError, match="headers"):
        load_config(config_file)


def test_load_config_preserves_command_substitution_in_product_credentials(
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
        token = "$(example-token-helper)"
        """.strip()
    )

    config = load_config(config_file)

    assert config.product_config(Product.JIRA).token == "$(example-token-helper)"


def test_load_config_rejects_legacy_profiles_table(tmp_path: Path) -> None:
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

    with pytest.raises(
        ConfigError,
        match=r"Profile-based config \[profiles\.\*\] has been removed",
    ):
        load_config(config_file)


def test_load_raw_config_data_preserves_unresolved_placeholders_and_tables(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "${ATLASSIAN_SOURCE}"

        [jira]
        deployment = "${ATLASSIAN_DEPLOYMENT}"
        url = "https://${ATLASSIAN_HOST}"
        auth = "${ATLASSIAN_AUTH}"

        [jira.headers]
        Authorization = "Bearer $(example-token-helper --host ${ATLASSIAN_HOST})"
        """.strip()
    )

    raw_config = load_raw_config_data(config_file)

    assert raw_config == {
        "headers": {
            "X-Request-Source": "${ATLASSIAN_SOURCE}",
        },
        "jira": {
            "deployment": "${ATLASSIAN_DEPLOYMENT}",
            "url": "https://${ATLASSIAN_HOST}",
            "auth": "${ATLASSIAN_AUTH}",
            "headers": {
                "Authorization": "Bearer $(example-token-helper --host ${ATLASSIAN_HOST})",
            },
        },
    }


def test_load_raw_config_data_rejects_legacy_profiles_table(tmp_path: Path) -> None:
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

    with pytest.raises(
        ConfigError,
        match=r"Profile-based config \[profiles\.\*\] has been removed",
    ):
        load_raw_config_data(config_file)


def test_load_raw_config_data_wraps_toml_decode_errors(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('headers = "unterminated')

    with pytest.raises(ConfigError, match=r"Invalid config\.toml configuration:"):
        load_raw_config_data(config_file)
