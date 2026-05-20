import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from atlassian_cli.config.models import LoadedConfig
from atlassian_cli.core.errors import ConfigError


def load_raw_config_data(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid config.toml configuration: {exc}") from exc
    if "profiles" in data:
        raise ConfigError(
            "Profile-based config [profiles.*] has been removed. "
            "Migrate to top-level [jira], [confluence], or [bitbucket]."
        )
    return data


def load_config(path: Path) -> LoadedConfig:
    data = load_raw_config_data(path)
    try:
        return LoadedConfig(
            headers=data.get("headers", {}),
            jira=data.get("jira"),
            confluence=data.get("confluence"),
            bitbucket=data.get("bitbucket"),
        )
    except ValidationError as exc:
        raise ConfigError(f"Invalid config.toml configuration: {exc}") from exc
