import datetime as dt
import json
import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from atlassian_cli.config.models import Product, ProductConfig
from atlassian_cli.config.template import DEFAULT_CONFIG_TEMPLATE
from atlassian_cli.core.errors import ConfigError

PRODUCT_TABLES = {product.value for product in Product}
KNOWN_TABLES = PRODUCT_TABLES | {"headers"}
BARE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ConfigWriteError(ConfigError):
    pass


def product_config_exists(path: Path, product: Product) -> bool:
    if not path.exists():
        return False
    data = _read_toml(path)
    return _product_configured(data, product)


def write_product_config(
    path: Path,
    product: Product,
    product_config: ProductConfig,
    *,
    force: bool = False,
) -> None:
    force_products = {product} if force else set()
    write_product_configs(path, {product: product_config}, force_products=force_products)


def write_product_configs(
    path: Path,
    updates: dict[Product, ProductConfig],
    *,
    force_products: set[Product] | None = None,
) -> None:
    force_products = force_products or set()
    data = _read_or_default(path)
    for product in updates:
        if _product_configured(data, product) and product not in force_products:
            raise ConfigWriteError(
                f"[{product.value}] already exists. Use --force to overwrite it."
            )

    _atomic_write(path, _render_config_data(_merge_product_updates(data, updates)))


def _merge_product_updates(
    data: dict[str, Any],
    updates: dict[Product, ProductConfig],
) -> dict[str, Any]:
    merged = dict(data)
    if not isinstance(merged.get("headers"), dict):
        merged["headers"] = {}

    for product in Product:
        if product in updates:
            merged[product.value] = _product_config_to_data(updates[product])
        elif not _product_configured(data, product):
            merged.pop(product.value, None)
    return merged


def _read_or_default(path: Path) -> dict[str, Any]:
    if path.exists():
        return _read_toml(path)
    return tomllib.loads(DEFAULT_CONFIG_TEMPLATE)


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigWriteError(f"Invalid config.toml configuration: {exc}") from exc
    if "profiles" in data:
        raise ConfigWriteError(
            "Profile-based config [profiles.*] has been removed. "
            "Migrate to top-level [jira], [confluence], or [bitbucket]."
        )
    return data


def _product_configured(data: dict[str, Any], product: Product) -> bool:
    table = data.get(product.value)
    if not isinstance(table, dict):
        return False
    if any(key != "headers" for key in table):
        return True
    headers = table.get("headers")
    return isinstance(headers, dict) and bool(headers)


def _product_config_to_data(product_config: ProductConfig) -> dict[str, Any]:
    values = product_config.model_dump(exclude_none=True)
    headers = values.pop("headers", {})
    if headers:
        values["headers"] = headers
    return values


def _render_config_data(data: dict[str, Any]) -> str:
    sections: list[str] = []
    root_values = {
        key: value
        for key, value in data.items()
        if not isinstance(value, dict) and key not in KNOWN_TABLES
    }
    if root_values:
        sections.append(_render_values(root_values))

    sections.append(_render_table(("headers",), _table_values(data.get("headers"))))
    for product in Product:
        table = data.get(product.value)
        if not isinstance(table, dict):
            continue
        values = dict(table)
        headers = values.pop("headers", {})
        sections.append(_render_table((product.value,), values))
        if headers:
            sections.append(_render_table((product.value, "headers"), headers))
        for key, value in values.items():
            if isinstance(value, dict):
                sections.extend(_render_unknown_table((product.value, key), value))

    for key, value in data.items():
        if key in KNOWN_TABLES or not isinstance(value, dict):
            continue
        sections.extend(_render_unknown_table((key,), value))
    return "\n\n".join(section.rstrip() for section in sections).rstrip() + "\n"


def _render_table(path: tuple[str, ...], values: dict[str, Any]) -> str:
    lines = [f"[{_format_toml_table_path(path)}]"]
    rendered_values = _render_values(values)
    if rendered_values:
        lines.append(rendered_values)
    return "\n".join(lines) + "\n"


def _render_values(values: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, dict):
            continue
        lines.append(f"{_format_toml_key(key)} = {_format_toml_value(value)}")
    return "\n".join(lines)


def _render_unknown_table(path: tuple[str, ...], table: dict[str, Any]) -> list[str]:
    sections: list[str] = []
    values = _render_values(table)
    if values or not table:
        sections.append(_render_table(path, table))
    for key, value in table.items():
        if isinstance(value, dict):
            sections.extend(_render_unknown_table((*path, key), value))
    return sections


def _table_values(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _format_toml_key(key: str) -> str:
    if BARE_KEY_PATTERN.fullmatch(key):
        return key
    return _format_toml_string(key)


def _format_toml_table_path(path: tuple[str, ...]) -> str:
    return ".".join(_format_toml_key(part) for part in path)


def _format_toml_value(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    return _format_toml_string(str(value))


def _format_toml_string(value: str) -> str:
    return json.dumps(value)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write(text)
        os.replace(tmp_name, path)
    except OSError as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise ConfigWriteError(f"Could not write {path}: {exc}") from exc
