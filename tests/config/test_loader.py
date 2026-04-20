from pathlib import Path

import pytest

from atlassian_cli.config.loader import load_profiles
from atlassian_cli.core.errors import UnsupportedError


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
