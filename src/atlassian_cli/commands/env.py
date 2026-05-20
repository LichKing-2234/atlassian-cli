import os
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from atlassian_cli.config.env_interpolation import (
    resolve_active_product_input,
    resolve_default_headers,
)
from atlassian_cli.config.header_substitution import resolve_header_map
from atlassian_cli.config.loader import load_raw_config_data
from atlassian_cli.config.models import Product, ProductConfig
from atlassian_cli.core.errors import ConfigError

PRODUCT_FIELDS = ("deployment", "url", "auth", "username", "password", "token")


def _normalize_header_name(name: str) -> str:
    normalized: list[str] = []
    previous_was_underscore = False
    previous_was_lowercase = False
    for char in name:
        if char.isascii() and char.isalnum():
            if char.isupper() and previous_was_lowercase and not previous_was_underscore:
                normalized.append("_")
            normalized.append(char.upper())
            previous_was_underscore = False
            previous_was_lowercase = char.islower()
        else:
            if normalized and not previous_was_underscore:
                normalized.append("_")
            previous_was_underscore = True
            previous_was_lowercase = False
    return "".join(normalized).strip("_")


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _export_line(name: str, value: Any) -> str:
    rendered = value.value if hasattr(value, "value") else value
    return f"export {name}={_shell_quote('' if rendered is None else str(rendered))}"


def _header_export_name(prefix: str, header_name: str) -> str:
    normalized_name = _normalize_header_name(header_name)
    if not normalized_name:
        raise ConfigError(f"Header name normalizes to empty export suffix: {header_name}")
    return f"{prefix}{normalized_name}"


def _append_export_line(lines: list[str], seen_names: set[str], name: str, value: Any) -> None:
    if name in seen_names:
        raise ConfigError(f"Duplicate export name: {name}")
    seen_names.add(name)
    lines.append(_export_line(name, value))


def env_command(ctx: typer.Context) -> None:
    config_file = Path(ctx.find_root().params["config_file"])
    env = dict(os.environ)
    lines: list[str] = []
    seen_names: set[str] = set()

    try:
        raw_config = load_raw_config_data(config_file) if config_file.exists() else {}
        for header_name, header_value in resolve_header_map(
            resolve_default_headers(raw_config, env=env),
            source="[headers]",
        ).items():
            _append_export_line(
                lines,
                seen_names,
                _header_export_name("ATLASSIAN_HEADER_", header_name),
                header_value,
            )

        for product in Product:
            resolved = resolve_active_product_input(raw_config, product=product, env=env)
            prefix = f"ATLASSIAN_{product.value.upper()}"
            if not resolved.product_data:
                continue
            product_config = ProductConfig(
                **resolved.product_data, headers=resolved.product_headers
            )
            for field in PRODUCT_FIELDS:
                value = getattr(product_config, field)
                if value is not None:
                    _append_export_line(
                        lines,
                        seen_names,
                        f"{prefix}_{field.upper()}",
                        value,
                    )
            for header_name, header_value in resolve_header_map(
                resolved.product_headers,
                source=f"[{product.value}.headers]",
            ).items():
                _append_export_line(
                    lines,
                    seen_names,
                    _header_export_name(f"{prefix}_HEADER_", header_name),
                    header_value,
                )
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo("\n".join(lines), nl=bool(lines))
