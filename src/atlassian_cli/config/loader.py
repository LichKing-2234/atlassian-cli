from pathlib import Path
import tomllib

from pydantic import ValidationError

from atlassian_cli.config.models import Deployment, LoadedConfig, ProfileConfig
from atlassian_cli.core.errors import ConfigError, UnsupportedError


def load_config(path: Path) -> LoadedConfig:
    data = tomllib.loads(path.read_text())
    raw_profiles = data.get("profiles", {})
    profiles: dict[str, ProfileConfig] = {}
    try:
        for name, raw in raw_profiles.items():
            profile = ProfileConfig(name=name, **raw)
            if profile.deployment is Deployment.CLOUD:
                raise UnsupportedError("Cloud profiles are reserved for a future release")
            profiles[name] = profile
        return LoadedConfig(
            headers=data.get("headers", {}),
            profiles=profiles,
        )
    except ValidationError as exc:
        raise ConfigError(f"Invalid config.toml headers configuration: {exc}") from exc


def load_profiles(path: Path) -> dict[str, ProfileConfig]:
    return load_config(path).profiles
