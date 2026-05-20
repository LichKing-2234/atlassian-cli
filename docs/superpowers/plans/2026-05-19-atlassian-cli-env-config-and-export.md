# Atlassian CLI Environment-Backed Config and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `${VAR_NAME}`-backed config resolution, `atlassian init --env-template`, and `atlassian env` shell exports without breaking existing CLI flag precedence or header command substitution.

**Architecture:** Parse raw TOML before Pydantic validation so enum-backed fields such as `deployment` and `auth` can be populated from `${...}` references, and resolve only the active product block plus relevant headers during normal product-command execution. Keep `$(...)` execution restricted to header values after `${...}` interpolation, extend the config writer with a raw-table path so `init --env-template` can write placeholder strings for enum-backed fields, and implement `atlassian env` as a local utility that resolves configured products into shell-safe `export` lines without calling product APIs.

**Tech Stack:** Python 3.12, Typer, Pydantic, `tomllib`, pytest, `CliRunner`, ruff

---

## Planned File Structure

### Create

- `src/atlassian_cli/config/env_interpolation.py`
  - Owns `${...}` parsing, variable-name validation, source-aware interpolation errors, active-product config resolution, and header env expansion before `$(...)`.
- `src/atlassian_cli/commands/env.py`
  - Owns `atlassian env`, export-name normalization, POSIX shell quoting, and the no-partial-output contract.
- `tests/config/test_env_interpolation.py`
  - Covers interpolation semantics, active-product scoping, and source-aware failures.
- `tests/test_env_command.py`
  - Covers end-to-end CLI export behavior, normalized header names, quoting, and failure handling.

### Modify

- `src/atlassian_cli/config/loader.py`
  - Add a raw TOML loader that product commands and `atlassian env` can use before model validation.
- `src/atlassian_cli/config/resolver.py`
  - Keep runtime precedence logic, but switch product-header error sources from removed profile paths to real `[product.headers]` paths.
- `src/atlassian_cli/config/template.py`
  - Update the default generated template to commented `${...}` examples.
- `src/atlassian_cli/config/writer.py`
  - Add a raw product-table write path so `init --env-template` can persist enum-backed placeholder strings such as `${ATLASSIAN_JIRA_DEPLOYMENT}`.
- `src/atlassian_cli/commands/init.py`
  - Add `--env-template`, skip credential prompts in that mode, and route template writes through raw table updates.
- `src/atlassian_cli/cli.py`
  - Register the new `env` command and switch product-command config loading to the raw -> interpolate -> validate flow.
- `tests/config/test_loader.py`
  - Cover the new raw loader behavior and keep literal-config coverage for `load_config()`.
- `tests/config/test_resolver.py`
  - Cover product-header resolution after `${...}` interpolation and updated source paths.
- `tests/config/test_template.py`
  - Assert the default template now advertises `${...}` examples instead of literal secrets.
- `tests/config/test_writer.py`
  - Cover raw-table writes used by `init --env-template`.
- `tests/test_init_command.py`
  - Cover `--env-template` behavior, overwrite protections, and no-prompt flows.
- `tests/test_cli_context.py`
  - Cover env-backed product resolution in normal commands and active-product scoping.
- `tests/test_cli_help.py`
  - Assert root help exposes `env`.
- `tests/test_readme.py`
  - Assert README documents environment-backed config and the export workflow.
- `tests/e2e/support/context.py`
  - Make live support context construction use the same raw interpolation path as real commands.
- `tests/e2e/test_support.py`
  - Cover env-backed config in the local e2e support helper.
- `tests/e2e/coverage_manifest.py`
  - Add `env` to the command-surface manifest, mapped to a local automated owner test.
- `README.md`
  - Document `${...}` config, `init --env-template`, `eval "$(atlassian env)"`, and the distinction from `$(...)` header substitution.

### Common Commands

- Focused interpolation tests: `.venv/bin/python -m pytest tests/config/test_env_interpolation.py tests/config/test_loader.py -v`
- Focused runtime tests: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/test_cli_context.py tests/e2e/test_support.py -v`
- Focused init/template tests: `.venv/bin/python -m pytest tests/config/test_template.py tests/config/test_writer.py tests/test_init_command.py -v`
- Focused export tests: `.venv/bin/python -m pytest tests/test_env_command.py tests/test_cli_help.py tests/test_readme.py -v`
- Full local verification: `ruff format --check .`
- Full local verification: `.venv/bin/python -m pytest -q`
- Full local verification: `ruff check README.md pyproject.toml src tests docs`

## Task 1: Add Raw Config Loading and `${...}` Interpolation

**Files:**
- Create: `src/atlassian_cli/config/env_interpolation.py`
- Modify: `src/atlassian_cli/config/loader.py`
- Modify: `tests/config/test_loader.py`
- Test: `tests/config/test_env_interpolation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_env_interpolation.py`:

```python
from atlassian_cli.config.env_interpolation import (
    interpolate_env_value,
    resolve_active_product_input,
)
from atlassian_cli.config.models import Product
from atlassian_cli.core.errors import ConfigError


def test_resolve_active_product_input_interpolates_product_fields_and_headers() -> None:
    raw = {
        "headers": {"X-Request-Source": "${ATLASSIAN_HEADER_SOURCE}"},
        "jira": {
            "deployment": "${ATLASSIAN_JIRA_DEPLOYMENT}",
            "url": "https://${ATLASSIAN_JIRA_HOST}",
            "auth": "${ATLASSIAN_JIRA_AUTH}",
            "username": "${ATLASSIAN_JIRA_USERNAME}",
            "token": "${ATLASSIAN_JIRA_TOKEN}",
            "headers": {
                "Authorization": "Bearer ${ATLASSIAN_JIRA_BEARER}",
                "accessToken": "$(example-oauth token --host ${ATLASSIAN_JIRA_HOST})",
            },
        },
    }

    resolved = resolve_active_product_input(
        raw,
        product=Product.JIRA,
        env={
            "ATLASSIAN_HEADER_SOURCE": "env-source",
            "ATLASSIAN_JIRA_DEPLOYMENT": "server",
            "ATLASSIAN_JIRA_HOST": "jira.example.com",
            "ATLASSIAN_JIRA_AUTH": "basic",
            "ATLASSIAN_JIRA_USERNAME": "example-user",
            "ATLASSIAN_JIRA_TOKEN": "secret",
            "ATLASSIAN_JIRA_BEARER": "bearer-token",
        },
    )

    assert resolved.product_data == {
        "deployment": "server",
        "url": "https://jira.example.com",
        "auth": "basic",
        "username": "example-user",
        "token": "secret",
    }
    assert resolved.default_headers == {"X-Request-Source": "env-source"}
    assert resolved.product_headers == {
        "Authorization": "Bearer bearer-token",
        "accessToken": "$(example-oauth token --host jira.example.com)",
    }


def test_resolve_active_product_input_only_resolves_selected_product() -> None:
    raw = {
        "jira": {
            "deployment": "server",
            "url": "https://jira.example.com",
            "auth": "basic",
            "token": "secret",
        },
        "confluence": {
            "deployment": "${ATLASSIAN_CONFLUENCE_DEPLOYMENT}",
            "url": "${ATLASSIAN_CONFLUENCE_URL}",
            "auth": "${ATLASSIAN_CONFLUENCE_AUTH}",
        },
    }

    resolved = resolve_active_product_input(raw, product=Product.JIRA, env={})

    assert resolved.product_data["url"] == "https://jira.example.com"


def test_interpolate_env_value_rejects_missing_variable_with_source() -> None:
    try:
        interpolate_env_value("${ATLASSIAN_JIRA_TOKEN}", source="[jira].token", env={})
    except ConfigError as exc:
        assert str(exc) == "Missing environment variable ATLASSIAN_JIRA_TOKEN for [jira].token"
    else:
        raise AssertionError("expected ConfigError")


def test_interpolate_env_value_rejects_malformed_reference() -> None:
    try:
        interpolate_env_value("${ATLASSIAN-JIRA-TOKEN}", source="[jira].token", env={})
    except ConfigError as exc:
        assert str(exc) == "Malformed environment interpolation in [jira].token"
    else:
        raise AssertionError("expected ConfigError")
```

Update the import block in `tests/config/test_loader.py`:

```python
from atlassian_cli.config.loader import load_config, load_raw_config_data
```

Add to `tests/config/test_loader.py`:

```python
def test_load_raw_config_data_rejects_legacy_profiles_table(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        """.strip()
    )

    with pytest.raises(
        ConfigError,
        match=r"Profile-based config \[profiles\.\*\] has been removed",
    ):
        load_raw_config_data(config_file)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_env_interpolation.py tests/config/test_loader.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.config.env_interpolation` and `ImportError` for `load_raw_config_data`

- [ ] **Step 3: Write the minimal implementation**

Create `src/atlassian_cli/config/env_interpolation.py`:

```python
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from atlassian_cli.config.models import Product
from atlassian_cli.core.errors import ConfigError

_ENV_REFERENCE = re.compile(r"\$\{([^}]+)\}")
_VALID_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ResolvedProductInput:
    product_data: dict[str, str]
    default_headers: dict[str, str]
    product_headers: dict[str, str]


def interpolate_env_value(value: str, *, source: str, env: Mapping[str, str]) -> str:
    if "${" in value and not _ENV_REFERENCE.search(value):
        raise ConfigError(f"Malformed environment interpolation in {source}")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if not _VALID_ENV_NAME.fullmatch(name):
            raise ConfigError(f"Malformed environment interpolation in {source}")
        if name not in env:
            raise ConfigError(f"Missing environment variable {name} for {source}")
        return env[name]

    return _ENV_REFERENCE.sub(replace, value)


def _resolve_string_map(
    raw_map: dict[str, Any],
    *,
    source: str,
    env: Mapping[str, str],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, value in raw_map.items():
        field_source = f"{source}.{key}"
        if not isinstance(value, str):
            raise ConfigError(f"Invalid config.toml configuration: {field_source} must be a string")
        resolved[key] = interpolate_env_value(value, source=field_source, env=env)
    return resolved


def _as_table(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("Invalid config.toml configuration: expected table data")
    return value


def resolve_default_headers(
    raw_config: dict[str, Any],
    *,
    env: Mapping[str, str],
) -> dict[str, str]:
    return _resolve_string_map(_as_table(raw_config.get("headers")), source="[headers]", env=env)


def resolve_active_product_input(
    raw_config: dict[str, Any],
    *,
    product: Product,
    env: Mapping[str, str],
) -> ResolvedProductInput:
    default_headers = resolve_default_headers(raw_config, env=env)
    product_table = _as_table(raw_config.get(product.value))
    product_headers = _resolve_string_map(
        _as_table(product_table.get("headers")),
        source=f"[{product.value}.headers]",
        env=env,
    )
    product_values = {key: value for key, value in product_table.items() if key != "headers"}
    return ResolvedProductInput(
        product_data=_resolve_string_map(product_values, source=f"[{product.value}]", env=env),
        default_headers=default_headers,
        product_headers=product_headers,
    )
```

Update `src/atlassian_cli/config/loader.py`:

```python
import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from atlassian_cli.config.models import LoadedConfig
from atlassian_cli.core.errors import ConfigError


def load_raw_config_data(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid config.toml configuration: {exc}") from exc
    if "profiles" in data:
        raise ConfigError(
            "Profile-based config [profiles.*] has been removed. "
            "Migrate to top-level [jira], [confluence], or [bitbucket]."
        )
    return data


def load_config(path: Path) -> LoadedConfig:
    data = load_raw_config_data(path)
    try:
        return LoadedConfig(
            headers=data.get("headers", {}),
            jira=data.get("jira"),
            confluence=data.get("confluence"),
            bitbucket=data.get("bitbucket"),
        )
    except ValidationError as exc:
        raise ConfigError(f"Invalid config.toml configuration: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_env_interpolation.py tests/config/test_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/env_interpolation.py src/atlassian_cli/config/loader.py tests/config/test_env_interpolation.py tests/config/test_loader.py
git commit -m "feat: add env-backed config interpolation"
```

## Task 2: Wire Product Commands and Live Helpers to the Raw Resolution Path

**Files:**
- Modify: `src/atlassian_cli/config/resolver.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/config/test_resolver.py`
- Modify: `tests/test_cli_context.py`
- Modify: `tests/e2e/support/context.py`
- Modify: `tests/e2e/test_support.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/config/test_resolver.py`:

```python
import pytest

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.core.errors import ConfigError


def test_product_headers_use_real_product_source_path() -> None:
    profile = ProfileConfig(
        name="jira",
        product=Product.JIRA,
        deployment=Deployment.SERVER,
        url="https://jira.example.com",
        auth=AuthMode.BASIC,
        token="secret",
        headers={"Authorization": "$(example-oauth token)"},
    )

    with pytest.raises(
        ConfigError,
        match=r"Header command produced empty output for \[jira.headers\]\.Authorization",
    ):
        resolve_runtime_context(
            profile=profile,
            env={},
            default_headers={},
            overrides=RuntimeOverrides(product=Product.JIRA, output="json"),
            command_runner=lambda command: "",
        )
```

Add to `tests/test_cli_context.py`:

```python
def test_root_callback_resolves_env_backed_product_fields_before_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
        url = "https://${ATLASSIAN_JIRA_HOST}"
        auth = "${ATLASSIAN_JIRA_AUTH}"
        username = "${ATLASSIAN_JIRA_USERNAME}"
        token = "${ATLASSIAN_JIRA_TOKEN}"
        """.strip()
    )

    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda context: type(
            "FakeService",
            (),
            {
                "get": lambda self, issue_key: {
                    "key": issue_key,
                    "url": context.url,
                    "auth": context.auth.mode.value,
                    "username": context.auth.username,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "jira", "issue", "get", "DEMO-1", "--output", "json"],
        env={
            **ci_output_env(),
            "ATLASSIAN_JIRA_DEPLOYMENT": "server",
            "ATLASSIAN_JIRA_HOST": "jira.example.com",
            "ATLASSIAN_JIRA_AUTH": "basic",
            "ATLASSIAN_JIRA_USERNAME": "example-user",
            "ATLASSIAN_JIRA_TOKEN": "secret",
        },
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout
    assert '"auth": "basic"' in result.stdout
    assert '"username": "example-user"' in result.stdout


def test_root_callback_only_resolves_active_product_block(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        token = "secret"

        [confluence]
        deployment = "${ATLASSIAN_CONFLUENCE_DEPLOYMENT}"
        url = "${ATLASSIAN_CONFLUENCE_URL}"
        auth = "${ATLASSIAN_CONFLUENCE_AUTH}"
        token = "${ATLASSIAN_CONFLUENCE_TOKEN}"
        """.strip()
    )

    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda context: type("FakeService", (), {"get": lambda self, issue_key: {"url": context.url}})(),
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "jira", "issue", "get", "DEMO-1", "--output", "json"],
        env=ci_output_env(),
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout
```

Update `tests/e2e/test_support.py`:

```python
def test_build_live_context_reads_env_backed_product_config(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
        url = "https://${ATLASSIAN_JIRA_HOST}"
        auth = "${ATLASSIAN_JIRA_AUTH}"
        username = "${ATLASSIAN_JIRA_USERNAME}"
        token = "${ATLASSIAN_JIRA_TOKEN}"
        """.strip()
    )
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("ATLASSIAN_JIRA_DEPLOYMENT", "server")
    monkeypatch.setenv("ATLASSIAN_JIRA_HOST", "jira.example.com")
    monkeypatch.setenv("ATLASSIAN_JIRA_AUTH", "basic")
    monkeypatch.setenv("ATLASSIAN_JIRA_USERNAME", "example-user")
    monkeypatch.setenv("ATLASSIAN_JIRA_TOKEN", "secret")

    env = load_live_env()
    context = build_live_context(Product.JIRA, env)

    assert context.url == "https://jira.example.com"
    assert context.auth.username == "example-user"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/test_cli_context.py tests/e2e/test_support.py -v`
Expected: FAIL because product commands still validate literal config before `${...}` resolution, resolver still reports `[profiles.*.headers]`, and live support still calls `load_config()` directly

- [ ] **Step 3: Write the minimal implementation**

Update `src/atlassian_cli/config/resolver.py`:

```python
from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.config.header_substitution import resolve_header_map
from atlassian_cli.core.context import ExecutionContext


def resolve_runtime_context(
    *,
    profile,
    env: dict[str, str],
    default_headers: dict[str, str] | None = None,
    overrides,
    command_runner=None,
):
    product = overrides.product or profile.product
    deployment = overrides.deployment or profile.deployment
    url = overrides.url or env.get("ATLASSIAN_URL") or profile.url
    username = overrides.username or env.get("ATLASSIAN_USERNAME") or profile.username
    password = overrides.password or env.get("ATLASSIAN_PASSWORD") or profile.password
    token = overrides.token or env.get("ATLASSIAN_TOKEN") or profile.token
    auth = overrides.auth or profile.auth
    config_headers = resolve_header_map(default_headers or {}, source="[headers]", runner=command_runner)
    product_headers = resolve_header_map(
        profile.headers,
        source=f"[{product.value}.headers]",
        runner=command_runner,
    )
    headers = {**config_headers, **product_headers, **overrides.headers}
    return ExecutionContext(
        profile=overrides.profile or profile.name,
        product=product,
        deployment=deployment,
        url=url,
        output=overrides.output,
        auth=resolve_auth(
            auth=auth,
            username=username,
            password=password,
            token=token,
            headers=headers,
        ),
    )
```

Update the config-loading branch inside `src/atlassian_cli/cli.py`:

```python
from atlassian_cli.config.env_interpolation import resolve_active_product_input
from atlassian_cli.config.loader import load_raw_config_data
from atlassian_cli.config.models import ProductConfig, ProfileConfig, RuntimeOverrides


def load_runtime_context():
    created_template = ensure_default_config(config_file, default_path=DEFAULT_CONFIG_FILE)
    raw_config = load_raw_config_data(config_file) if config_file.exists() else {}
    resolved_input = resolve_active_product_input(raw_config, product=product, env=dict(os.environ))

    if resolved_input.product_data:
        try:
            product_config = ProductConfig(
                **resolved_input.product_data,
                headers=resolved_input.product_headers,
            )
            base_profile = product_config.to_profile_config(product=product, name=product.value)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    elif url is None:
        raise typer.BadParameter(_missing_product_message(config_file, product, created=created_template))
    else:
        base_profile = ProfileConfig(
            name=f"inline-{product.value}",
            product=product,
            deployment=deployment or Deployment.SERVER,
            url=url,
            auth=auth or AuthMode.BASIC,
            username=username,
            password=password,
            token=token,
            headers={},
        )

    return resolve_runtime_context(
        profile=base_profile,
        env=dict(os.environ),
        default_headers=resolved_input.default_headers,
        overrides=RuntimeOverrides(
            product=product,
            deployment=deployment,
            url=url,
            username=username,
            password=password,
            token=token,
            auth=auth,
            headers=headers,
            output=output,
        ),
    )
```

Update `tests/e2e/support/context.py`:

```python
import os

from atlassian_cli.config.env_interpolation import resolve_active_product_input
from atlassian_cli.config.loader import load_raw_config_data
from atlassian_cli.config.models import Product, ProductConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.products.factory import build_provider
from tests.e2e.support.env import LiveEnv


def build_live_context(product: Product, live_env: LiveEnv):
    raw_config = load_raw_config_data(live_env.config_file)
    resolved_input = resolve_active_product_input(raw_config, product=product, env=dict(os.environ))
    if not resolved_input.product_data:
        raise AssertionError(f"missing [{product.value}] config in {live_env.config_file}")
    profile = ProductConfig(
        **resolved_input.product_data,
        headers=resolved_input.product_headers,
    ).to_profile_config(product=product, name=product.value)
    return resolve_runtime_context(
        profile=profile,
        env=dict(os.environ),
        default_headers=resolved_input.default_headers,
        overrides=RuntimeOverrides(product=product, output="json"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/test_cli_context.py tests/e2e/test_support.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/resolver.py src/atlassian_cli/cli.py tests/config/test_resolver.py tests/test_cli_context.py tests/e2e/support/context.py tests/e2e/test_support.py
git commit -m "feat: resolve env-backed product config at runtime"
```

## Task 3: Add Raw-Table Writing and `init --env-template`

**Files:**
- Modify: `src/atlassian_cli/config/writer.py`
- Modify: `src/atlassian_cli/config/template.py`
- Modify: `src/atlassian_cli/commands/init.py`
- Modify: `tests/config/test_writer.py`
- Modify: `tests/config/test_template.py`
- Modify: `tests/test_init_command.py`

- [ ] **Step 1: Write the failing tests**

Update the import block in `tests/config/test_writer.py`:

```python
from atlassian_cli.config.writer import (
    ConfigWriteError,
    product_config_exists,
    write_product_config,
    write_product_configs,
    write_product_tables,
)
```

Add to `tests/config/test_writer.py`:

```python
def test_write_product_tables_supports_env_template_placeholders(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    write_product_tables(
        config_file,
        {
            Product.JIRA: {
                "deployment": "${ATLASSIAN_JIRA_DEPLOYMENT}",
                "url": "${ATLASSIAN_JIRA_URL}",
                "auth": "${ATLASSIAN_JIRA_AUTH}",
                "username": "${ATLASSIAN_JIRA_USERNAME}",
                "password": "${ATLASSIAN_JIRA_PASSWORD}",
                "token": "${ATLASSIAN_JIRA_TOKEN}",
                "headers": {
                    "Authorization": "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}",
                },
            }
        },
    )

    assert config_file.read_text() == (
        "[headers]\n"
        "\n"
        "[jira]\n"
        'deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"\n'
        'url = "${ATLASSIAN_JIRA_URL}"\n'
        'auth = "${ATLASSIAN_JIRA_AUTH}"\n'
        'username = "${ATLASSIAN_JIRA_USERNAME}"\n'
        'password = "${ATLASSIAN_JIRA_PASSWORD}"\n'
        'token = "${ATLASSIAN_JIRA_TOKEN}"\n'
        "\n"
        "[jira.headers]\n"
        'Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"\n'
    )
```

Update `tests/config/test_template.py`:

```python
def test_default_config_template_uses_env_placeholder_examples() -> None:
    assert '# deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# url = "${ATLASSIAN_JIRA_URL}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"' in DEFAULT_CONFIG_TEMPLATE
    assert '# token = "secret"' not in DEFAULT_CONFIG_TEMPLATE
```

Add to `tests/test_init_command.py`:

```python
def test_init_env_template_single_product_writes_placeholders(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "jira", "--env-template", "--config-file", str(config_file)],
    )

    assert result.exit_code == 0
    assert f"Wrote [jira] to {config_file}" in result.stdout
    text = config_file.read_text()
    assert 'deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"' in text
    assert 'url = "${ATLASSIAN_JIRA_URL}"' in text
    assert 'Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"' in text


def test_init_env_template_without_product_prompts_for_products_in_order(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["init", "--env-template", "--config-file", str(config_file)],
        input="y\nn\ny\n",
    )

    assert result.exit_code == 0
    assert result.stdout.index("Configure jira?") < result.stdout.index("Configure confluence?")
    assert result.stdout.index("Configure confluence?") < result.stdout.index("Configure bitbucket?")
    text = config_file.read_text()
    assert 'deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"' in text
    assert 'deployment = "${ATLASSIAN_BITBUCKET_DEPLOYMENT}"' in text
    assert "[confluence]" not in text


def test_init_env_template_preserves_overwrite_protection(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        ["init", "jira", "--env-template", "--config-file", str(config_file)],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Skipped [jira]." in result.stdout
    assert "${ATLASSIAN_JIRA_DEPLOYMENT}" not in config_file.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_writer.py tests/config/test_template.py tests/test_init_command.py -v`
Expected: FAIL because the writer has no raw-table API, the default template still uses literal examples, and `init` does not support `--env-template`

- [ ] **Step 3: Write the minimal implementation**

Update `src/atlassian_cli/config/writer.py`:

```python
def write_product_table(
    path: Path,
    product: Product,
    product_data: dict[str, Any],
    *,
    force: bool = False,
) -> None:
    force_products = {product} if force else set()
    write_product_tables(path, {product: product_data}, force_products=force_products)


def write_product_tables(
    path: Path,
    updates: dict[Product, dict[str, Any]],
    *,
    force_products: set[Product] | None = None,
) -> None:
    force_products = force_products or set()
    data = _read_or_default(path)
    for product in updates:
        if _product_configured(data, product) and product not in force_products:
            raise ConfigWriteError(f"[{product.value}] already exists. Use --force to overwrite it.")

    merged = dict(data)
    if not isinstance(merged.get("headers"), dict):
        merged["headers"] = {}
    for product in Product:
        if product in updates:
            merged[product.value] = updates[product]
        elif not _product_configured(data, product):
            merged.pop(product.value, None)
    _atomic_write(path, _render_config_data(merged))


def write_product_configs(
    path: Path,
    updates: dict[Product, ProductConfig],
    *,
    force_products: set[Product] | None = None,
) -> None:
    table_updates = {
        product: _product_config_to_data(product_config)
        for product, product_config in updates.items()
    }
    write_product_tables(path, table_updates, force_products=force_products)
```

Update `src/atlassian_cli/config/template.py`:

```python
DEFAULT_CONFIG_TEMPLATE = """[headers]
# X-Request-Source = "${ATLASSIAN_HEADER_X_REQUEST_SOURCE}"

[jira]
# deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
# url = "${ATLASSIAN_JIRA_URL}"
# auth = "${ATLASSIAN_JIRA_AUTH}"
# username = "${ATLASSIAN_JIRA_USERNAME}"
# password = "${ATLASSIAN_JIRA_PASSWORD}"
# token = "${ATLASSIAN_JIRA_TOKEN}"

[jira.headers]
# Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"

[confluence]
# deployment = "${ATLASSIAN_CONFLUENCE_DEPLOYMENT}"
# url = "${ATLASSIAN_CONFLUENCE_URL}"
# auth = "${ATLASSIAN_CONFLUENCE_AUTH}"
# username = "${ATLASSIAN_CONFLUENCE_USERNAME}"
# password = "${ATLASSIAN_CONFLUENCE_PASSWORD}"
# token = "${ATLASSIAN_CONFLUENCE_TOKEN}"

[confluence.headers]
# Authorization = "${ATLASSIAN_CONFLUENCE_HEADER_AUTHORIZATION}"

[bitbucket]
# deployment = "${ATLASSIAN_BITBUCKET_DEPLOYMENT}"
# url = "${ATLASSIAN_BITBUCKET_URL}"
# auth = "${ATLASSIAN_BITBUCKET_AUTH}"
# username = "${ATLASSIAN_BITBUCKET_USERNAME}"
# password = "${ATLASSIAN_BITBUCKET_PASSWORD}"
# token = "${ATLASSIAN_BITBUCKET_TOKEN}"

[bitbucket.headers]
# Authorization = "${ATLASSIAN_BITBUCKET_HEADER_AUTHORIZATION}"
# accessToken = "$(example-oauth token --host ${ATLASSIAN_BITBUCKET_URL})"
"""
```

Update `src/atlassian_cli/commands/init.py`:

```python
from typing import Any

from atlassian_cli.config.writer import (
    ConfigWriteError,
    product_config_exists,
    write_product_configs,
    write_product_tables,
)


def init_command(
    product: Product | None = typer.Argument(None),
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, "--config-file", help="Path to config.toml."),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    force: bool = typer.Option(False, "--force"),
    env_template: bool = typer.Option(False, "--env-template"),
) -> None:
    products = [product] if product is not None else list(Product)
    literal_updates: dict[Product, ProductConfig] = {}
    template_updates: dict[Product, dict[str, Any]] = {}
    force_products: set[Product] = set()

    for selected_product in products:
        if product is None and not typer.confirm(f"Configure {selected_product.value}?", default=True):
            continue
        exists = product_config_exists(config_file, selected_product)
        if not force and exists and not _confirm_overwrite(selected_product):
            typer.echo(f"Skipped [{selected_product.value}].")
            continue
        if force or exists:
            force_products.add(selected_product)

        if env_template:
            template_updates[selected_product] = _build_env_template_table(selected_product)
        else:
            literal_updates[selected_product] = _build_product_config(
                deployment=deployment,
                url=url,
                auth=auth,
                username=username,
                password=password,
                token=token,
            )

    if not literal_updates and not template_updates:
        if product is None:
            typer.echo("No product config changed.")
        return

    try:
        if env_template:
            write_product_tables(config_file, template_updates, force_products=force_products)
        else:
            write_product_configs(config_file, literal_updates, force_products=force_products)
    except ConfigWriteError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _build_env_template_table(product: Product) -> dict[str, Any]:
    prefix = f"ATLASSIAN_{product.value.upper()}"
    return {
        "deployment": f"${{{prefix}_DEPLOYMENT}}",
        "url": f"${{{prefix}_URL}}",
        "auth": f"${{{prefix}_AUTH}}",
        "username": f"${{{prefix}_USERNAME}}",
        "password": f"${{{prefix}_PASSWORD}}",
        "token": f"${{{prefix}_TOKEN}}",
        "headers": {
            "Authorization": f"${{{prefix}_HEADER_AUTHORIZATION}}",
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_writer.py tests/config/test_template.py tests/test_init_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/writer.py src/atlassian_cli/config/template.py src/atlassian_cli/commands/init.py tests/config/test_writer.py tests/config/test_template.py tests/test_init_command.py
git commit -m "feat: add env template config initialization"
```

## Task 4: Add the `atlassian env` Export Command

**Files:**
- Create: `src/atlassian_cli/commands/env.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/test_cli_help.py`
- Modify: `tests/e2e/coverage_manifest.py`
- Test: `tests/test_env_command.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_env_command.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_env_command_exports_all_configured_product_values_and_headers(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "${ATLASSIAN_HEADER_SOURCE}"

        [jira]
        deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
        url = "${ATLASSIAN_JIRA_URL}"
        auth = "${ATLASSIAN_JIRA_AUTH}"
        username = "${ATLASSIAN_JIRA_USERNAME}"
        token = "${ATLASSIAN_JIRA_TOKEN}"

        [jira.headers]
        Authorization = "Bearer ${ATLASSIAN_JIRA_BEARER}"
        """.strip()
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "env"],
        env={
            "ATLASSIAN_HEADER_SOURCE": "env-source",
            "ATLASSIAN_JIRA_DEPLOYMENT": "server",
            "ATLASSIAN_JIRA_URL": "https://jira.example.com",
            "ATLASSIAN_JIRA_AUTH": "basic",
            "ATLASSIAN_JIRA_USERNAME": "example-user",
            "ATLASSIAN_JIRA_TOKEN": "secret",
            "ATLASSIAN_JIRA_BEARER": "bearer-token",
        },
    )

    assert result.exit_code == 0
    assert "export ATLASSIAN_JIRA_DEPLOYMENT='server'" in result.stdout
    assert "export ATLASSIAN_JIRA_URL='https://jira.example.com'" in result.stdout
    assert "export ATLASSIAN_JIRA_USERNAME='example-user'" in result.stdout
    assert "export ATLASSIAN_HEADER_X_REQUEST_SOURCE='env-source'" in result.stdout
    assert "export ATLASSIAN_JIRA_HEADER_AUTHORIZATION='Bearer bearer-token'" in result.stdout


def test_env_command_shell_quotes_single_quotes(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "${ATLASSIAN_JIRA_USERNAME}"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "env"],
        env={"ATLASSIAN_JIRA_USERNAME": "example'oauth"},
    )

    assert result.exit_code == 0
    assert "export ATLASSIAN_JIRA_USERNAME='example'\"'\"'oauth'" in result.stdout


def test_env_command_fails_without_partial_stdout(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "${ATLASSIAN_JIRA_URL}"
        auth = "basic"
        token = "secret"
        """.strip()
    )

    result = runner.invoke(app, ["--config-file", str(config_file), "env"])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Missing environment variable ATLASSIAN_JIRA_URL for [jira].url" in result.output
```

Update `tests/test_cli_help.py`:

```python
def test_root_help_displays_products_and_local_config_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "jira" in result.stdout
    assert "confluence" in result.stdout
    assert "bitbucket" in result.stdout
    assert "init" in result.stdout
    assert "env" in result.stdout
    assert "update" in result.stdout
```

Update `tests/e2e/coverage_manifest.py`:

```python
    "env": "test_env_command_exports_all_configured_product_values_and_headers",
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_env_command.py tests/test_cli_help.py -v`
Expected: FAIL because there is no `env` command and root help does not list it

- [ ] **Step 3: Write the minimal implementation**

Create `src/atlassian_cli/commands/env.py`:

```python
import os
from typing import Any

import typer

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
            if char.isupper() and index and name[index - 1].islower() and not previous_was_underscore:
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
    config_file = ctx.find_root().params["config_file"]
    env = dict(os.environ)
    raw_config = load_raw_config_data(config_file) if config_file.exists() else {}
    lines: list[str] = []

    try:
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
            product_config = ProductConfig(**resolved.product_data, headers=resolved.product_headers)
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

    typer.echo("\n".join(lines), nl=bool(lines))
```

Update the top-level registration in `src/atlassian_cli/cli.py`:

```python
from atlassian_cli.commands.env import env_command

app.command("env")(env_command)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_env_command.py tests/test_cli_help.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/commands/env.py src/atlassian_cli/cli.py tests/test_env_command.py tests/test_cli_help.py tests/e2e/coverage_manifest.py
git commit -m "feat: add env export command"
```

## Task 5: Update README, Assertions, and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`

- [ ] **Step 1: Write the failing documentation assertions**

Add to `tests/test_readme.py`:

```python
def test_readme_mentions_environment_backed_config_and_env_command() -> None:
    readme = Path("README.md").read_text()

    assert "${ATLASSIAN_JIRA_URL}" in readme
    assert "atlassian init jira --env-template" in readme
    assert 'eval "$(atlassian env)"' in readme
    assert "environment-backed config" in readme.lower()
    assert "$(example-oauth token --host ${ATLASSIAN_BITBUCKET_URL})" in readme
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_readme.py -v`
Expected: FAIL because README does not yet mention `${...}`, `--env-template`, or `atlassian env`

- [ ] **Step 3: Update the README**

Add this section to `README.md` after `## Configure`:

````markdown
### Environment-backed config

Generate placeholder-based product config instead of storing literal credentials:

```bash
atlassian init jira --env-template
```

Example `config.toml`:

```toml
[headers]
X-Request-Source = "${ATLASSIAN_HEADER_X_REQUEST_SOURCE}"

[jira]
deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
url = "${ATLASSIAN_JIRA_URL}"
auth = "${ATLASSIAN_JIRA_AUTH}"
username = "${ATLASSIAN_JIRA_USERNAME}"
token = "${ATLASSIAN_JIRA_TOKEN}"

[jira.headers]
Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"

[bitbucket.headers]
accessToken = "$(example-oauth token --host ${ATLASSIAN_BITBUCKET_URL})"
```

`${...}` reads from the current process environment. `$(...)` is still supported only for header values in trusted local config.

Export the resolved config into a POSIX shell environment:

```bash
eval "$(atlassian env)"
```
````

- [ ] **Step 4: Run focused doc tests and full repository verification**

Run: `.venv/bin/python -m pytest tests/test_readme.py tests/test_env_command.py tests/test_cli_help.py tests/config/test_env_interpolation.py tests/config/test_loader.py tests/config/test_resolver.py tests/config/test_template.py tests/config/test_writer.py tests/test_init_command.py tests/test_cli_context.py tests/e2e/test_support.py -v`
Expected: PASS

Run: `ruff format --check .`
Expected: PASS

Run: `.venv/bin/python -m pytest -q`
Expected: PASS

Run: `ruff check README.md pyproject.toml src tests docs`
Expected: PASS

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_jira_live.py::test_jira_project_and_metadata_live tests/e2e/test_confluence_live.py::test_confluence_space_and_search_live tests/e2e/test_bitbucket_live.py::test_bitbucket_project_and_repo_queries_live -v`
Expected: PASS if the live Atlassian environment is available; if it is not, stop and report the live-e2e blocker explicitly instead of claiming live verification

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: document env-backed config workflows"
```

## Self-Review Checklist

- Spec coverage:
  - `${...}` interpolation for product fields and headers is covered in Task 1.
  - Active-product-only resolution and real command wiring are covered in Task 2.
  - `init --env-template` and the default config template are covered in Task 3.
  - `atlassian env`, export naming, shell quoting, and no-partial-output behavior are covered in Task 4.
  - README, help, coverage manifest, and verification are covered in Tasks 4 and 5.
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” markers remain.
  - Every code-edit step includes concrete code or exact README text.
- Type consistency:
  - The plan consistently uses `ResolvedProductInput`, `resolve_active_product_input()`, `load_raw_config_data()`, `write_product_tables()`, and `env_command()`.
  - Raw-table writes are isolated from `ProductConfig` so enum-backed placeholders are never forced through the validated model too early.

Plan complete and saved to `docs/superpowers/plans/2026-05-19-atlassian-cli-env-config-and-export.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
