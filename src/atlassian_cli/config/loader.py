from pathlib import Path
import tomllib

from atlassian_cli.config.models import Deployment, ProfileConfig
from atlassian_cli.core.errors import UnsupportedError


def load_profiles(path: Path) -> dict[str, ProfileConfig]:
    data = tomllib.loads(path.read_text())
    raw_profiles = data.get("profiles", {})
    profiles: dict[str, ProfileConfig] = {}
    for name, raw in raw_profiles.items():
        profile = ProfileConfig(name=name, **raw)
        if profile.deployment is Deployment.CLOUD:
            raise UnsupportedError("Cloud profiles are reserved for a future release")
        profiles[name] = profile
    return profiles
