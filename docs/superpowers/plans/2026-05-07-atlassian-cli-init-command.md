# Atlassian CLI Init Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `atlassian init [PRODUCT]` so users can create or update product config interactively or through flags.

**Architecture:** Keep runtime config loading unchanged. Add a focused config writer for the supported public TOML shape, then add a top-level Typer command that gathers init input, validates `ProductConfig`, and writes selected product blocks without touching product API commands.

**Tech Stack:** Python 3.12, Typer, Pydantic, `tomllib`, pytest `CliRunner`, ruff.

---

## File Structure

- Create `src/atlassian_cli/config/writer.py`
  - Owns local config file creation and deterministic serialization of the supported config shape.
- Exposes `write_product_config(path, product, product_config, force=False)`, `write_product_configs(path, updates, force_products=None)`, and `product_config_exists(path, product)`.
- Create `tests/config/test_writer.py`
  - Covers preserving headers/unrelated product blocks, replacing target product blocks, creating missing files, and refusing overwrite without force.
- Create `src/atlassian_cli/commands/init.py`
  - Owns the `atlassian init [PRODUCT]` command, prompt flow, non-interactive validation, and friendly errors.
- Create `tests/test_init_command.py`
  - Covers CLI behavior through `CliRunner`.
- Modify `src/atlassian_cli/cli.py`
  - Register the top-level `init` command and keep root runtime config resolution limited to product commands.
- Modify `tests/test_cli_help.py`
  - Assert root help lists `init`.
- Modify `README.md`
  - Document the recommended first setup command and non-interactive examples.
- Modify `tests/test_readme.py`
  - Assert README mentions `atlassian init`.

## Task 1: Config Writer

**Files:**
- Create: `src/atlassian_cli/config/writer.py`
- Test: `tests/config/test_writer.py`

- [ ] **Step 1: Write failing writer tests**

Create `tests/config/test_writer.py`:

```python
from pathlib import Path

import pytest

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Deployment, Product, ProductConfig
from atlassian_cli.config.writer import (
    ConfigWriteError,
    product_config_exists,
    write_product_config,
    write_product_configs,
)


def test_write_product_config_creates_new_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"

    write_product_config(
        config_file,
        Product.JIRA,
        ProductConfig(
            deployment=Deployment.SERVER,
            url="https://jira.example.com",
            auth=AuthMode.BASIC,
            username="example-user",
            token="secret",
        ),
    )

    config = load_config(config_file)
    jira = config.product_config(Product.JIRA)
    assert jira is not None
    assert jira.deployment is Deployment.SERVER
    assert jira.url == "https://jira.example.com"
    assert jira.auth is AuthMode.BASIC
    assert jira.username == "example-user"
    assert jira.token == "secret"
    assert config.headers == {}


def test_write_product_config_preserves_headers_and_other_products(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "example-oauth"

        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "old-token"
        """.strip()
    )

    write_product_config(
        config_file,
        Product.CONFLUENCE,
        ProductConfig(
            deployment=Deployment.DC,
            url="https://confluence.example.com",
            auth=AuthMode.PAT,
            token="secret",
        ),
    )

    config = load_config(config_file)
    assert config.headers == {"X-Request-Source": "example-oauth"}
    assert config.product_config(Product.JIRA).url == "https://jira.example.com"
    assert config.product_config(Product.BITBUCKET).url == "https://bitbucket.example.com"
    assert config.product_config(Product.CONFLUENCE).url == "https://confluence.example.com"


def test_write_product_config_refuses_existing_product_without_force(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    original = """
    [jira]
    deployment = "server"
    url = "https://jira.example.com"
    auth = "basic"
    username = "example-user"
    token = "secret"
    """.strip()
    config_file.write_text(original)

    with pytest.raises(ConfigWriteError, match=r"\\[jira\\] already exists"):
        write_product_config(
            config_file,
            Product.JIRA,
            ProductConfig(
                deployment=Deployment.DC,
                url="https://jira-new.example.com",
                auth=AuthMode.PAT,
                token="new-secret",
            ),
        )

    assert config_file.read_text() == original


def test_write_product_config_replaces_existing_product_with_force(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"
        """.strip()
    )

    write_product_config(
        config_file,
        Product.JIRA,
        ProductConfig(
            deployment=Deployment.DC,
            url="https://jira-new.example.com",
            auth=AuthMode.PAT,
            token="new-secret",
        ),
        force=True,
    )

    text = config_file.read_text()
    config = load_config(config_file)
    jira = config.product_config(Product.JIRA)
    assert jira.deployment is Deployment.DC
    assert jira.url == "https://jira-new.example.com"
    assert jira.auth is AuthMode.PAT
    assert jira.username is None
    assert jira.token == "new-secret"
    assert "username" not in text


def test_write_product_configs_writes_multiple_products_in_one_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    write_product_configs(
        config_file,
        {
            Product.JIRA: ProductConfig(
                deployment=Deployment.SERVER,
                url="https://jira.example.com",
                auth=AuthMode.BASIC,
                username="example-user",
                token="secret",
            ),
            Product.BITBUCKET: ProductConfig(
                deployment=Deployment.DC,
                url="https://bitbucket.example.com",
                auth=AuthMode.PAT,
                token="secret",
            ),
        },
    )

    config = load_config(config_file)
    assert config.product_config(Product.JIRA).url == "https://jira.example.com"
    assert config.product_config(Product.BITBUCKET).url == "https://bitbucket.example.com"
    assert config.product_config(Product.CONFLUENCE) is None


def test_product_config_exists_detects_configured_product(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        """.strip()
    )

    assert product_config_exists(config_file, Product.JIRA) is True
    assert product_config_exists(config_file, Product.CONFLUENCE) is False
    assert product_config_exists(tmp_path / "missing.toml", Product.JIRA) is False


def test_product_config_exists_ignores_empty_template_blocks(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]

        [jira.headers]
        """.strip()
    )

    assert product_config_exists(config_file, Product.JIRA) is False
```

- [ ] **Step 2: Run writer tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_writer.py -v`

Expected: FAIL with import error for `atlassian_cli.config.writer`.

- [ ] **Step 3: Implement config writer**

Create `src/atlassian_cli/config/writer.py`:

```python
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
    table = data.get(product.value)
    if not isinstance(table, dict):
        return False
    if any(key != "headers" for key in table):
        return True
    headers = table.get("headers")
    return isinstance(headers, dict) and bool(headers)


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
            raise ConfigWriteError(f"[{product.value}] already exists. Use --force to overwrite it.")

    loaded = LoadedConfig(
        headers=data.get("headers", {}),
        jira=_configured_table(data, Product.JIRA),
        confluence=_configured_table(data, Product.CONFLUENCE),
        bitbucket=_configured_table(data, Product.BITBUCKET),
    )
    for product, product_config in updates.items():
        setattr(loaded, product.value, product_config)
    text = _render_loaded_config(loaded)
    _atomic_write(path, text)


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
    return "\\n".join(section.rstrip() for section in sections).rstrip() + "\\n"


def _render_table(name: str, values: dict[str, Any]) -> str:
    lines = [f"[{name}]"]
    for key, value in values.items():
        if hasattr(value, "value"):
            value = value.value
        lines.append(f"{key} = {_format_toml_string(str(value))}")
    return "\\n".join(lines) + "\\n"


def _format_toml_string(value: str) -> str:
    escaped = value.replace("\\\\", "\\\\\\\\").replace('"', '\\"')
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
```

- [ ] **Step 4: Run writer tests**

Run: `.venv/bin/python -m pytest tests/config/test_writer.py -v`

Expected: PASS.

- [ ] **Step 5: Run existing config tests**

Run: `.venv/bin/python -m pytest tests/config/test_loader.py tests/config/test_template.py tests/config/test_resolver.py -v`

Expected: PASS.

- [ ] **Step 6: Commit config writer**

```bash
git add src/atlassian_cli/config/writer.py tests/config/test_writer.py
git commit -m "feat: add config writer"
```

## Task 2: Init Command Input Flow

**Files:**
- Create: `src/atlassian_cli/commands/init.py`
- Test: `tests/test_init_command.py`

- [ ] **Step 1: Write failing tests for single-product and non-interactive init**

Create `tests/test_init_command.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Product

runner = CliRunner()


def test_init_single_product_interactive_writes_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "jira", "--config-file", str(config_file)],
        input="server\\nhttps://jira.example.com\\nbasic\\nexample-user\\nsecret\\n",
    )

    assert result.exit_code == 0
    assert f"Wrote [jira] to {config_file}" in result.stdout
    config = load_config(config_file)
    jira = config.product_config(Product.JIRA)
    assert jira.deployment.value == "server"
    assert jira.url == "https://jira.example.com"
    assert jira.auth.value == "basic"
    assert jira.username == "example-user"
    assert jira.token == "secret"


def test_init_single_product_non_interactive_writes_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "init",
            "bitbucket",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
            "--url",
            "https://bitbucket.example.com",
            "--auth",
            "pat",
            "--token",
            "secret",
        ],
    )

    assert result.exit_code == 0
    config = load_config(config_file)
    bitbucket = config.product_config(Product.BITBUCKET)
    assert bitbucket.deployment.value == "dc"
    assert bitbucket.url == "https://bitbucket.example.com"
    assert bitbucket.auth.value == "pat"
    assert bitbucket.token == "secret"


def test_init_non_interactive_missing_required_values_fails_without_writing(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "init",
            "confluence",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
        ],
    )

    assert result.exit_code != 0
    assert "Missing required option for non-interactive init: --url" in result.output
    assert not config_file.exists()


def test_init_wizard_later_failure_does_not_write_partial_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "--config-file", str(config_file)],
        input=(
            "y\\n"
            "server\\n"
            "https://jira.example.com\\n"
            "basic\\n"
            "example-user\\n"
            "secret\\n"
            "y\\n"
        ),
    )

    assert result.exit_code != 0
    assert "Missing required option for non-interactive init: --deployment" in result.output
    assert not config_file.exists()


def test_init_rejects_existing_product_without_force_in_non_interactive_mode(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
            "--url",
            "https://jira-new.example.com",
            "--auth",
            "pat",
            "--token",
            "new-secret",
        ],
    )

    assert result.exit_code != 0
    assert "[jira] already exists" in result.output
    assert "https://jira-new.example.com" not in config_file.read_text()


def test_init_force_replaces_existing_product_in_non_interactive_mode(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(config_file),
            "--deployment",
            "dc",
            "--url",
            "https://jira-new.example.com",
            "--auth",
            "pat",
            "--token",
            "new-secret",
            "--force",
        ],
    )

    assert result.exit_code == 0
    jira = load_config(config_file).product_config(Product.JIRA)
    assert jira.deployment.value == "dc"
    assert jira.url == "https://jira-new.example.com"
    assert jira.auth.value == "pat"
    assert jira.username is None
    assert jira.token == "new-secret"
```

- [ ] **Step 2: Run init tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_init_command.py -v`

Expected: FAIL because the `init` command is not registered.

- [ ] **Step 3: Implement init command**

Create `src/atlassian_cli/commands/init.py`:

```python
from pathlib import Path

import click
import typer

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProductConfig
from atlassian_cli.config.writer import (
    ConfigWriteError,
    product_config_exists,
    write_product_configs,
)


def init_command(
    product: Product | None = typer.Argument(None),
    config_file: Path = typer.Option(
        Path("~/.config/atlassian-cli/config.toml").expanduser(),
        "--config-file",
        help="Path to config.toml.",
    ),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Create or update atlassian-cli config."""
    products = [product] if product is not None else list(Product)
    updates: dict[Product, ProductConfig] = {}
    force_products: set[Product] = set()
    for selected_product in products:
        if product is None and not typer.confirm(f"Configure {selected_product.value}?", default=True):
            continue
        exists = product_config_exists(config_file, selected_product)
        if (
            not force
            and exists
            and not _confirm_overwrite(selected_product)
        ):
            typer.echo(f"Skipped [{selected_product.value}].")
            continue
        if force or exists:
            force_products.add(selected_product)
        product_config = _build_product_config(
            deployment=deployment,
            url=url,
            auth=auth,
            username=username,
            password=password,
            token=token,
        )
        updates[selected_product] = product_config

    if not updates:
        if product is None:
            typer.echo("No product config changed.")
        return

    try:
        write_product_configs(config_file, updates, force_products=force_products)
    except ConfigWriteError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for selected_product in updates:
        typer.echo(f"Wrote [{selected_product.value}] to {config_file}")


def _confirm_overwrite(product: Product) -> bool:
    try:
        return typer.confirm(f"[{product.value}] already exists. Overwrite?", default=False)
    except click.Abort as exc:
        raise typer.BadParameter(
            f"[{product.value}] already exists. Use --force to overwrite it."
        ) from exc


def _build_product_config(
    *,
    deployment: Deployment | None,
    url: str | None,
    auth: AuthMode | None,
    username: str | None,
    password: str | None,
    token: str | None,
) -> ProductConfig:
    resolved_deployment = deployment or _prompt_enum("Deployment", Deployment)
    resolved_url = url or _prompt_value("URL", "--url")
    resolved_auth = auth or _prompt_enum("Auth", AuthMode)

    resolved_username = username
    resolved_password = password
    resolved_token = token
    if resolved_auth is AuthMode.BASIC:
        resolved_username = resolved_username or _prompt_value("Username", "--username")
        if resolved_password is None and resolved_token is None:
            resolved_token = _prompt_value("Token/password", "--token", hide_input=True)
    elif resolved_token is None:
        resolved_token = _prompt_value("Token", "--token", hide_input=True)

    return ProductConfig(
        deployment=resolved_deployment,
        url=resolved_url,
        auth=resolved_auth,
        username=resolved_username if resolved_auth is AuthMode.BASIC else None,
        password=resolved_password if resolved_auth is AuthMode.BASIC else None,
        token=resolved_token,
    )


def _prompt_enum(label: str, enum_type):
    option = "/".join(item.value for item in enum_type)
    value = _prompt_value(f"{label} ({option})", f"--{label.lower()}")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid {label.lower()}: {value}") from exc


def _prompt_value(label: str, option_name: str, *, hide_input: bool = False) -> str:
    try:
        return typer.prompt(label, hide_input=hide_input)
    except click.Abort as exc:
        raise typer.BadParameter(
            f"Missing required option for non-interactive init: {option_name}"
        ) from exc
```

- [ ] **Step 4: Register the command**

Modify `src/atlassian_cli/cli.py`:

```python
from atlassian_cli.commands.init import init_command
```

Then register it near the other top-level commands:

```python
app.command("init")(init_command)
```

Keep `PRODUCT_COMMANDS` unchanged so the root callback does not try to resolve runtime config for `init`.

- [ ] **Step 5: Run init tests**

Run: `.venv/bin/python -m pytest tests/test_init_command.py -v`

Expected: PASS.

- [ ] **Step 6: Commit init command**

```bash
git add src/atlassian_cli/commands/init.py src/atlassian_cli/cli.py tests/test_init_command.py
git commit -m "feat: add init command"
```

## Task 3: Full Wizard and Interactive Overwrite

**Files:**
- Modify: `tests/test_init_command.py`
- Modify: `src/atlassian_cli/commands/init.py`

- [ ] **Step 1: Add failing wizard and overwrite tests**

Append to `tests/test_init_command.py`:

```python
def test_init_without_product_prompts_for_products_in_order(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "--config-file", str(config_file)],
        input=(
            "y\\n"
            "server\\n"
            "https://jira.example.com\\n"
            "basic\\n"
            "example-user\\n"
            "secret\\n"
            "n\\n"
            "y\\n"
            "dc\\n"
            "https://bitbucket.example.com\\n"
            "pat\\n"
            "secret\\n"
        ),
    )

    assert result.exit_code == 0
    assert result.stdout.index("Configure jira?") < result.stdout.index("Configure confluence?")
    assert result.stdout.index("Configure confluence?") < result.stdout.index("Configure bitbucket?")
    config = load_config(config_file)
    assert config.product_config(Product.JIRA) is not None
    assert config.product_config(Product.CONFLUENCE) is None
    assert config.product_config(Product.BITBUCKET) is not None


def test_init_interactive_existing_product_decline_skips_without_writing(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    original = """
    [jira]
    deployment = "server"
    url = "https://jira.example.com"
    auth = "basic"
    username = "example-user"
    token = "secret"
    """.strip()
    config_file.write_text(original)

    result = runner.invoke(
        app,
        ["init", "jira", "--config-file", str(config_file)],
        input="n\\n",
    )

    assert result.exit_code == 0
    assert "Skipped [jira]." in result.stdout
    assert config_file.read_text() == original


def test_init_interactive_existing_product_confirm_overwrites(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "example-oauth"

        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        ["init", "jira", "--config-file", str(config_file)],
        input="y\\ndc\\nhttps://jira-new.example.com\\npat\\nnew-secret\\n",
    )

    assert result.exit_code == 0
    config = load_config(config_file)
    assert config.headers == {"X-Request-Source": "example-oauth"}
    jira = config.product_config(Product.JIRA)
    assert jira.deployment.value == "dc"
    assert jira.url == "https://jira-new.example.com"
    assert jira.auth.value == "pat"
    assert jira.username is None
    assert jira.token == "new-secret"
```

- [ ] **Step 2: Run the new tests to verify behavior**

Run: `.venv/bin/python -m pytest tests/test_init_command.py -v`

Expected: If Task 2 implementation already satisfies all wizard behavior, PASS. If it fails, failures should point to prompt text, overwrite flow, or force handling.

- [ ] **Step 3: Fix init flow if needed**

If prompt or overwrite tests fail, update `src/atlassian_cli/commands/init.py` to import `write_product_configs` from `atlassian_cli.config.writer` and keep this structure:

```python
def init_command(
    product: Product | None = typer.Argument(None),
    config_file: Path = typer.Option(
        Path("~/.config/atlassian-cli/config.toml").expanduser(),
        "--config-file",
        help="Path to config.toml.",
    ),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    products = [product] if product is not None else list(Product)
    updates: dict[Product, ProductConfig] = {}
    force_products: set[Product] = set()
    for selected_product in products:
        if product is None and not typer.confirm(f"Configure {selected_product.value}?", default=True):
            continue

        exists = product_config_exists(config_file, selected_product)
        if exists and not force:
            try:
                should_overwrite = typer.confirm(
                    f"[{selected_product.value}] already exists. Overwrite?",
                    default=False,
                )
            except click.Abort as exc:
                raise typer.BadParameter(
                    f"[{selected_product.value}] already exists. Use --force to overwrite it."
                ) from exc
            if not should_overwrite:
                typer.echo(f"Skipped [{selected_product.value}].")
                continue
            force_products.add(selected_product)
        elif force or exists:
            force_products.add(selected_product)

        product_config = _build_product_config(
            deployment=deployment,
            url=url,
            auth=auth,
            username=username,
            password=password,
            token=token,
        )
        updates[selected_product] = product_config

    if not updates:
        if product is None:
            typer.echo("No product config changed.")
        return

    write_product_configs(config_file, updates, force_products=force_products)
    for selected_product in updates:
        typer.echo(f"Wrote [{selected_product.value}] to {config_file}")
```

Do not prompt for product values until overwrite has been accepted.

- [ ] **Step 4: Run init tests again**

Run: `.venv/bin/python -m pytest tests/test_init_command.py -v`

Expected: PASS.

- [ ] **Step 5: Commit wizard behavior**

```bash
git add src/atlassian_cli/commands/init.py tests/test_init_command.py
git commit -m "feat: add init wizard flow"
```

## Task 4: Help and README

**Files:**
- Modify: `tests/test_cli_help.py`
- Modify: `tests/test_readme.py`
- Modify: `README.md`

- [ ] **Step 1: Add failing help and README tests**

Modify `tests/test_cli_help.py` in `test_root_help_displays_products`:

```python
def test_root_help_displays_products() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "jira" in result.stdout
    assert "confluence" in result.stdout
    assert "bitbucket" in result.stdout
    assert "init" in result.stdout
    assert "update" in result.stdout
    assert "--profile" not in result.stdout
```

Append to `tests/test_readme.py`:

```python
def test_readme_mentions_init_command() -> None:
    readme = Path("README.md").read_text()

    assert "atlassian init" in readme
    assert "atlassian init jira" in readme
    assert "--force" in readme
```

- [ ] **Step 2: Run tests to verify README failure if README is not updated**

Run: `.venv/bin/python -m pytest tests/test_cli_help.py tests/test_readme.py -v`

Expected: `test_readme_mentions_init_command` fails until README is updated. Help test should pass after Task 2 registration.

- [ ] **Step 3: Update README**

Insert this section after the install/update section and before `## Examples`:

````markdown
## Configure

Run the setup wizard:

```bash
atlassian init
```

Configure one product:

```bash
atlassian init jira
```

Use flags for non-interactive setup:

```bash
atlassian init bitbucket --deployment dc --url https://bitbucket.example.com --auth pat --token secret
```

Existing product config is not overwritten by default. Use `--force` when replacing a product block non-interactively:

```bash
atlassian init confluence --force --deployment server --url https://confluence.example.com --auth basic --username example-user --token secret
```

The default `~/.config/atlassian-cli/config.toml` file is still auto-created as a template on first product command when it does not already exist.
````

Use exactly the neutral example values shown above.

- [ ] **Step 4: Run help and README tests**

Run: `.venv/bin/python -m pytest tests/test_cli_help.py tests/test_readme.py -v`

Expected: PASS.

- [ ] **Step 5: Scan README for disallowed sample data introduced by this change**

Run: `rg -n "jira-new|\\bprod\\b|internal|@[A-Za-z0-9._-]+|[A-Z][A-Z]+-[0-9]+" README.md tests/test_readme.py tests/test_cli_help.py`

Expected: No output from new init examples except existing approved examples such as `DEMO-1` if present elsewhere in README.

- [ ] **Step 6: Commit docs and help**

```bash
git add README.md tests/test_cli_help.py tests/test_readme.py
git commit -m "docs: document init command"
```

## Task 5: Final Verification

**Files:**
- No planned code changes.

- [ ] **Step 1: Run targeted init/config tests**

Run:

```bash
.venv/bin/python -m pytest tests/config/test_writer.py tests/test_init_command.py tests/test_cli_help.py tests/test_readme.py -v
```

Expected: PASS.

- [ ] **Step 2: Run repository verification commands**

Run:

```bash
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: all commands exit 0.

- [ ] **Step 3: Check git status**

Run: `git status --short`

Expected: clean working tree after the task commits, or only unrelated user changes that were present before implementation.

- [ ] **Step 4: If verification fixes are needed, patch and commit**

If formatting or lint fails, run the minimal needed formatter or patch the exact failing files. Then run the failed verification command again.

Use this commit message for verification-only fixes:

```bash
git add src/atlassian_cli/config/writer.py src/atlassian_cli/commands/init.py src/atlassian_cli/cli.py tests/config/test_writer.py tests/test_init_command.py README.md tests/test_cli_help.py tests/test_readme.py
git commit -m "fix: polish init command"
```

Do not commit unrelated user changes.
