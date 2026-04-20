from pathlib import Path

import pytest

from atlassian_cli.config.loader import load_config, load_profiles
from atlassian_cli.core.errors import ConfigError, UnsupportedError


def test_load_profiles_reads_named_profiles(tmp_path: Path) -> None:
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

    profiles = load_profiles(config_file)

    assert profiles["prod_jira"].url == "https://jira.example.com"
    assert profiles["prod_jira"].deployment == "server"
    assert profiles["prod_jira"].headers == {}


def test_load_config_reads_top_level_and_profile_headers(tmp_path: Path) -> None:
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
        accessToken = "$(agora-oauth token --profile prod_bitbucket)"
        """.strip()
    )

    config = load_config(config_file)

    assert config.headers == {
        "X-Request-Source": "config-default",
    }
    assert config.profiles["prod_bitbucket"].headers == {
        "accessToken": "$(agora-oauth token --profile prod_bitbucket)",
    }


def test_load_config_rejects_non_string_header_values(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        accessToken = 42
        """.strip()
    )

    with pytest.raises(ConfigError, match="headers"):
        load_config(config_file)


def test_load_profiles_rejects_cloud_in_v1(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.cloud_jira]
        product = "jira"
        deployment = "cloud"
        url = "https://example.atlassian.net"
        auth = "basic"
        """.strip()
    )

    with pytest.raises(UnsupportedError):
        load_profiles(config_file)
