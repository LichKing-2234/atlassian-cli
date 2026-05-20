from pathlib import Path

from atlassian_cli.config.template import DEFAULT_CONFIG_TEMPLATE, ensure_default_config


def test_ensure_default_config_creates_template_for_default_path(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"

    created = ensure_default_config(config_file, default_path=config_file)

    assert created is True
    assert config_file.read_text() == DEFAULT_CONFIG_TEMPLATE


def test_ensure_default_config_does_not_create_custom_override_path(tmp_path: Path) -> None:
    default_path = tmp_path / "default" / "config.toml"
    custom_path = tmp_path / "custom.toml"

    created = ensure_default_config(custom_path, default_path=default_path)

    assert created is False
    assert not custom_path.exists()


def test_ensure_default_config_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text('[jira]\nurl = "https://jira.example.com"\n')

    created = ensure_default_config(config_file, default_path=config_file)

    assert created is False
    assert config_file.read_text() == '[jira]\nurl = "https://jira.example.com"\n'


def test_default_config_template_uses_only_top_level_product_blocks() -> None:
    assert "[jira]" in DEFAULT_CONFIG_TEMPLATE
    assert "[confluence]" in DEFAULT_CONFIG_TEMPLATE
    assert "[bitbucket]" in DEFAULT_CONFIG_TEMPLATE
    assert "[profiles." not in DEFAULT_CONFIG_TEMPLATE
    assert "Legacy compatibility" not in DEFAULT_CONFIG_TEMPLATE


def test_default_config_template_uses_env_placeholder_examples() -> None:
    assert '# url = "${ATLASSIAN_JIRA_URL}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# username = "${ATLASSIAN_JIRA_USERNAME}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# token = "${ATLASSIAN_JIRA_TOKEN}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# url = "${ATLASSIAN_CONFLUENCE_URL}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# token = "${ATLASSIAN_CONFLUENCE_TOKEN}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# url = "${ATLASSIAN_BITBUCKET_URL}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# token = "${ATLASSIAN_BITBUCKET_TOKEN}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# X-Request-Source = "${ATLASSIAN_HEADER_X_REQUEST_SOURCE}"' in DEFAULT_CONFIG_TEMPLATE
    assert (
        '# Authorization = "${ATLASSIAN_BITBUCKET_HEADER_AUTHORIZATION}"' in DEFAULT_CONFIG_TEMPLATE
    )
    assert '# token = "secret"' not in DEFAULT_CONFIG_TEMPLATE
