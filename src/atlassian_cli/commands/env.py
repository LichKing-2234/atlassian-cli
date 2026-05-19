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
    for index, char in enumerate(name):
        if char.isalnum():
            if (
                char.isupper()
                and index
                and name[index - 1].islower()
                and not previous_was_underscore
            ):
                normalized.append("_")
            normalized.append(char.upper())
            previous_was_underscore = False
        else:
            if not previous_was_underscore:
                normalized.append("_")
            previous_was_underscore = True
    return "".join(normalized).strip("_")


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _export_line(name: str, value: Any) -> str:
    rendered = value.value if hasattr(value, "value") else value
    return f"export {name}={_shell_quote('' if rendered is None else str(rendered))}"


def env_command(ctx: typer.Context) -> None:
    config_file = Path(ctx.find_root().params["config_file"])
    env = dict(os.environ)
    lines: list[str] = []

    try:
        raw_config = load_raw_config_data(config_file) if config_file.exists() else {}
        for header_name, header_value in resolve_header_map(
            resolve_default_headers(raw_config, env=env),
            source="[headers]",
        ).items():
            lines.append(
                _export_line(
                    f"ATLASSIAN_HEADER_{_normalize_header_name(header_name)}",
                    header_value,
                )
            )

        for product in Product:
            resolved = resolve_active_product_input(raw_config, product=product, env=env)
            if not resolved.product_data:
                continue
            product_config = ProductConfig(
                **resolved.product_data, headers=resolved.product_headers
            )
            prefix = f"ATLASSIAN_{product.value.upper()}"
            for field in PRODUCT_FIELDS:
                value = getattr(product_config, field)
                if value is not None:
                    lines.append(_export_line(f"{prefix}_{field.upper()}", value))
            for header_name, header_value in resolve_header_map(
                resolved.product_headers,
                source=f"[{product.value}.headers]",
            ).items():
                lines.append(
                    _export_line(
                        f"{prefix}_HEADER_{_normalize_header_name(header_name)}",
                        header_value,
                    )
                )
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo("\n".join(lines), nl=bool(lines))
