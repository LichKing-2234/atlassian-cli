from pathlib import Path
import tomllib

from pydantic import ValidationError

from atlassian_cli.config.models import LoadedConfig
from atlassian_cli.core.errors import ConfigError


def load_config(path: Path) -> LoadedConfig:
    data = tomllib.loads(path.read_text())
    if "profiles" in data:
        raise ConfigError(
            "Profile-based config [profiles.*] has been removed. "
            "Migrate to top-level [jira], [confluence], or [bitbucket]."
        )
    try:
        return LoadedConfig(
            headers=data.get("headers", {}),
            jira=data.get("jira"),
            confluence=data.get("confluence"),
            bitbucket=data.get("bitbucket"),
        )
    except ValidationError as exc:
        raise ConfigError(f"Invalid config.toml configuration: {exc}") from exc
