import os
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from atlassian_cli.config.models import LoadedConfig, Product, ProductConfig
from atlassian_cli.config.template import DEFAULT_CONFIG_TEMPLATE
from atlassian_cli.core.errors import ConfigError


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

    loaded = LoadedConfig(
        headers=data.get("headers", {}),
        jira=_configured_table(data, Product.JIRA),
        confluence=_configured_table(data, Product.CONFLUENCE),
        bitbucket=_configured_table(data, Product.BITBUCKET),
    )
    for product, product_config in updates.items():
        setattr(loaded, product.value, product_config)
    _atomic_write(path, _render_loaded_config(loaded))


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


def _configured_table(data: dict[str, Any], product: Product) -> dict[str, Any] | None:
    if not _product_configured(data, product):
        return None
    table = dict(data[product.value])
    if table.get("headers") == {}:
        table.pop("headers")
    return table


def _render_loaded_config(config: LoadedConfig) -> str:
    sections: list[str] = []
    sections.append(_render_table("headers", config.headers))
    for product in Product:
        product_config = config.product_config(product)
        if product_config is None:
            continue
        values = product_config.model_dump(exclude_none=True)
        headers = values.pop("headers", {})
        sections.append(_render_table(product.value, values))
        if headers:
            sections.append(_render_table(f"{product.value}.headers", headers))
    return "\n".join(section.rstrip() for section in sections).rstrip() + "\n"


def _render_table(name: str, values: dict[str, Any]) -> str:
    lines = [f"[{name}]"]
    for key, value in values.items():
        if hasattr(value, "value"):
            value = value.value
        lines.append(f"{key} = {_format_toml_string(str(value))}")
    return "\n".join(lines) + "\n"


def _format_toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


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
