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
