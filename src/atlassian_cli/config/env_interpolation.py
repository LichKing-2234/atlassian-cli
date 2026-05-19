import re
from dataclasses import dataclass
from typing import Any

from atlassian_cli.core.errors import ConfigError

_ENV_REFERENCE = re.compile(r"\$\{([^}]+)\}")
_VALID_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True)
class ResolvedProductInput:
    product_data: dict[str, Any]
    default_headers: dict[str, str]
    product_headers: dict[str, str]


def interpolate_env_value(value: str, *, source: str, env: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        if not _VALID_ENV_NAME.fullmatch(variable_name):
            raise ConfigError(f"Malformed environment interpolation in {source}")
        if variable_name not in env:
            raise ConfigError(f"Missing environment variable '{variable_name}' for {source}")
        return env[variable_name]

    return _ENV_REFERENCE.sub(replace, value)


def _resolve_string_map(
    raw_map: dict[str, Any],
    *,
    source: str,
    env: dict[str, str],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name, value in raw_map.items():
        if not isinstance(value, str):
            raise ConfigError(
                f"Invalid config.toml configuration: {source}.{name} must be a string"
            )
        resolved[name] = interpolate_env_value(value, source=f"{source}.{name}", env=env)
    return resolved


def _as_table(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("Invalid config.toml configuration: expected TOML table")
    return value


def resolve_default_headers(raw_config: dict[str, Any], *, env: dict[str, str]) -> dict[str, str]:
    return _resolve_string_map(
        _as_table(raw_config.get("headers")),
        source="[headers]",
        env=env,
    )


def resolve_active_product_input(
    raw_config: dict[str, Any],
    *,
    product,
    env: dict[str, str],
) -> ResolvedProductInput:
    default_headers = resolve_default_headers(raw_config, env=env)
    product_table = _as_table(raw_config.get(product.value))
    product_headers = _resolve_string_map(
        _as_table(product_table.get("headers")),
        source=f"[{product.value}].headers",
        env=env,
    )
    product_data = {
        field_name: (
            interpolate_env_value(field_value, source=f"[{product.value}].{field_name}", env=env)
            if isinstance(field_value, str)
            else field_value
        )
        for field_name, field_value in product_table.items()
        if field_name != "headers"
    }
    return ResolvedProductInput(
        product_data=product_data,
        default_headers=default_headers,
        product_headers=product_headers,
    )
