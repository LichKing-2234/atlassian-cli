import re
from dataclasses import dataclass
from typing import Any

from atlassian_cli.config.models import Product
from atlassian_cli.core.errors import ConfigError

_ENV_REFERENCE = re.compile(r"\$\{([^}]+)\}")
_VALID_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True)
class ResolvedProductInput:
    product_data: dict[str, str]
    default_headers: dict[str, str]
    product_headers: dict[str, str]


def interpolate_env_value(value: str, *, source: str, env: dict[str, str]) -> str:
    resolved: list[str] = []
    current_index = 0
    while True:
        start_index = value.find("${", current_index)
        if start_index == -1:
            resolved.append(value[current_index:])
            return "".join(resolved)

        resolved.append(value[current_index:start_index])
        end_index = value.find("}", start_index + 2)
        if end_index == -1:
            raise ConfigError(f"Malformed environment interpolation in {source}")

        reference = value[start_index : end_index + 1]
        match = _ENV_REFERENCE.fullmatch(reference)
        if match is None:
            raise ConfigError(f"Malformed environment interpolation in {source}")

        variable_name = match.group(1)
        if not _VALID_ENV_NAME.fullmatch(variable_name):
            raise ConfigError(f"Malformed environment interpolation in {source}")
        if variable_name not in env:
            raise ConfigError(f"Missing environment variable {variable_name} for {source}")

        resolved.append(env[variable_name])
        current_index = end_index + 1


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


def _as_table(value: Any, *, source: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"Invalid config.toml configuration: {source} must be a TOML table")
    return value


def resolve_default_headers(raw_config: dict[str, Any], *, env: dict[str, str]) -> dict[str, str]:
    return _resolve_string_map(
        _as_table(raw_config.get("headers"), source="[headers]"),
        source="[headers]",
        env=env,
    )


def resolve_active_product_input(
    raw_config: dict[str, Any],
    *,
    product: Product,
    env: dict[str, str],
) -> ResolvedProductInput:
    default_headers = resolve_default_headers(raw_config, env=env)
    product_table = _as_table(raw_config.get(product.value), source=f"[{product.value}]")
    product_headers = _resolve_string_map(
        _as_table(product_table.get("headers"), source=f"[{product.value}.headers]"),
        source=f"[{product.value}.headers]",
        env=env,
    )
    product_fields = {
        field_name: field_value
        for field_name, field_value in product_table.items()
        if field_name != "headers"
    }
    base_field_names = ("deployment", "url", "auth", "token")
    product_data = _resolve_string_map(
        {
            field_name: product_fields[field_name]
            for field_name in base_field_names
            if field_name in product_fields
        },
        source=f"[{product.value}]",
        env=env,
    )
    if product_data.get("auth") == "basic" and "username" in product_fields:
        product_data["username"] = interpolate_env_value(
            product_fields["username"],
            source=f"[{product.value}].username",
            env=env,
        )
    if product_data.get("auth") == "basic" and "password" in product_fields:
        product_data["password"] = interpolate_env_value(
            product_fields["password"],
            source=f"[{product.value}].password",
            env=env,
        )
    return ResolvedProductInput(
        product_data=product_data,
        default_headers=default_headers,
        product_headers=product_headers,
    )
