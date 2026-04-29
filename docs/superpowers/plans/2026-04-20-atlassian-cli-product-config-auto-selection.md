# Atlassian CLI Product Config Auto-Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-create a default `config.toml` template and let `jira`, `confluence`, and `bitbucket` commands read product-specific top-level config blocks without requiring `--profile`.

**Architecture:** Add a small config template helper that only creates the default config path on first use, extend the loaded config model to parse top-level `[jira]`, `[confluence]`, and `[bitbucket]` blocks, and change the CLI entrypoint to choose the product-matching block unless `--profile` explicitly selects a legacy profile. Keep header resolution in the existing runtime resolver so `[headers]`, `[product.headers]`, and repeated `--header` keep the current precedence.

**Tech Stack:** Python 3.13, Typer, Pydantic, atlassian-python-api, pytest

---

## Planned File Structure

### Create

- `src/atlassian_cli/config/template.py`
- `tests/config/test_template.py`

### Modify

- `src/atlassian_cli/config/models.py`
- `src/atlassian_cli/config/loader.py`
- `src/atlassian_cli/cli.py`
- `tests/config/test_loader.py`
- `tests/test_cli_context.py`
- `README.md`

### Responsibility Notes

- `config/template.py` owns the first-run default template content and the helper that creates it only for the default config path.
- `config/models.py` owns the typed representation of top-level product config blocks and the conversion path from product config to runtime `ProfileConfig`.
- `config/loader.py` owns parsing both top-level product blocks and legacy profiles into one loaded config object.
- `cli.py` owns config initialization, product-based auto-selection, legacy `--profile` compatibility, and user-facing error messages.
- `config/resolver.py` stays unchanged because it already merges config-backed headers with CLI flags once it receives a resolved base config.

### Common Commands

- Template tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_template.py -v`
- Loader tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_loader.py -v`
- CLI context tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_cli_context.py -v`
- Full suite: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest -q`

## Task 1: Add Default Config Template Creation

**Files:**
- Create: `src/atlassian_cli/config/template.py`
- Create: `tests/config/test_template.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from atlassian_cli.config.template import DEFAULT_CONFIG_TEMPLATE, ensure_default_config


def test_ensure_default_config_creates_template_for_default_path(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"

    created = ensure_default_config(config_file, default_path=config_file)

    assert created is True
    assert config_file.read_text() == DEFAULT_CONFIG_TEMPLATE


def test_ensure_default_config_does_not_create_custom_override_path(tmp_path: Path) -> None:
    default_path = tmp_path / "default" / "config.toml"
    custom_path = tmp_path / "custom.toml"

    created = ensure_default_config(custom_path, default_path=default_path)

    assert created is False
    assert not custom_path.exists()


def test_ensure_default_config_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("[jira]\nurl = \"https://jira.example.com\"\n")

    created = ensure_default_config(config_file, default_path=config_file)

    assert created is False
    assert config_file.read_text() == "[jira]\nurl = \"https://jira.example.com\"\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_template.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlassian_cli.config.template'`

- [ ] **Step 3: Write the minimal implementation**

```python
from pathlib import Path


DEFAULT_CONFIG_TEMPLATE = """[headers]
# accessToken = "$(example-oauth token)"

[jira]
# deployment = "server"
# url = "https://jira.example.com"
# auth = "basic"
# username = "example-user"
# token = "secret"

[jira.headers]
# accessToken = "$(example-oauth token)"

[confluence]
# deployment = "dc"
# url = "https://confluence.example.com"
# auth = "pat"
# token = "secret"

[confluence.headers]
# accessToken = "$(example-oauth token)"

[bitbucket]
# deployment = "dc"
# url = "https://bitbucket.example.com"
# auth = "pat"
# token = "secret"

[bitbucket.headers]
# accessToken = "$(example-oauth token)"

# Legacy compatibility:
#
# [profiles.prod_jira]
# product = "jira"
# deployment = "server"
# url = "https://jira.example.com"
# auth = "basic"
"""


def ensure_default_config(path: Path, *, default_path: Path) -> bool:
    if path != default_path or path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/template.py tests/config/test_template.py
git commit -m "feat: add default config template helper"
```

## Task 2: Parse Top-Level Product Config Blocks

**Files:**
- Modify: `src/atlassian_cli/config/models.py`
- Modify: `src/atlassian_cli/config/loader.py`
- Modify: `tests/config/test_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from atlassian_cli.config.loader import load_config, load_profiles
from atlassian_cli.config.models import Product, ProductConfig
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.core.errors import ConfigError, UnsupportedError


def test_load_config_reads_top_level_product_sections(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [jira]
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"

        [jira.headers]
        accessToken = "$(example-oauth token)"

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"
        """.strip()
    )

    config = load_config(config_file)

    assert config.headers == {"X-Request-Source": "config-default"}
    assert config.product_config(Product.JIRA).url == "https://jira.example.com"
    assert config.product_config(Product.JIRA).headers == {
        "accessToken": "$(example-oauth token)",
    }
    assert config.product_config(Product.BITBUCKET).auth is AuthMode.PAT


def test_product_config_to_profile_config_requires_deployment_url_and_auth() -> None:
    product_config = ProductConfig(url="https://jira.example.com")

    with pytest.raises(ConfigError, match="missing required fields"):
        product_config.to_profile_config(product=Product.JIRA, name="jira")
```

```python
from pathlib import Path

import pytest

from atlassian_cli.config.loader import load_config, load_profiles
from atlassian_cli.core.errors import ConfigError, UnsupportedError


def test_load_profiles_reads_named_profiles(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "example-user"
        token = "secret"
        """.strip()
    )

    profiles = load_profiles(config_file)

    assert profiles["prod_jira"].url == "https://jira.example.com"
    assert profiles["prod_jira"].deployment == "server"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_loader.py -v`
Expected: FAIL because `LoadedConfig` has no top-level product fields or `product_config()` helper

- [ ] **Step 3: Write the minimal implementation**

```python
from enum import StrEnum

from pydantic import BaseModel, Field, StrictStr

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.core.errors import ConfigError


class Product(StrEnum):
    JIRA = "jira"
    CONFLUENCE = "confluence"
    BITBUCKET = "bitbucket"


class Deployment(StrEnum):
    SERVER = "server"
    DC = "dc"
    CLOUD = "cloud"


class ProductConfig(BaseModel):
    deployment: Deployment | None = None
    url: StrictStr | None = None
    auth: AuthMode | None = None
    username: StrictStr | None = None
    password: StrictStr | None = None
    token: StrictStr | None = None
    headers: dict[str, StrictStr] = Field(default_factory=dict)

    def to_profile_config(self, *, product: Product, name: str) -> "ProfileConfig":
        missing = [
            field
            for field in ("deployment", "url", "auth")
            if getattr(self, field) is None
        ]
        if missing:
            raise ConfigError(
                f"Product config [{product.value}] is missing required fields: {', '.join(missing)}"
            )
        return ProfileConfig(
            name=name,
            product=product,
            deployment=self.deployment,
            url=self.url,
            auth=self.auth,
            username=self.username,
            password=self.password,
            token=self.token,
            headers=self.headers,
        )


class ProfileConfig(BaseModel):
    name: str
    product: Product
    deployment: Deployment
    url: str
    auth: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None
    headers: dict[str, StrictStr] = Field(default_factory=dict)


class LoadedConfig(BaseModel):
    headers: dict[str, StrictStr] = Field(default_factory=dict)
    jira: ProductConfig | None = None
    confluence: ProductConfig | None = None
    bitbucket: ProductConfig | None = None
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    def product_config(self, product: Product) -> ProductConfig | None:
        if product is Product.JIRA:
            return self.jira
        if product is Product.CONFLUENCE:
            return self.confluence
        return self.bitbucket
```

```python
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
            jira=data.get("jira"),
            confluence=data.get("confluence"),
            bitbucket=data.get("bitbucket"),
            profiles=profiles,
        )
    except ValidationError as exc:
        raise ConfigError(f"Invalid config.toml configuration: {exc}") from exc


def load_profiles(path: Path) -> dict[str, ProfileConfig]:
    return load_config(path).profiles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/models.py src/atlassian_cli/config/loader.py tests/config/test_loader.py
git commit -m "feat: parse top-level product config blocks"
```

## Task 3: Auto-Select Product Config in the CLI

**Files:**
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/test_cli_context.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import atlassian_cli.cli as cli_module
import atlassian_cli.config.header_substitution as header_substitution
from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.config.models import LoadedConfig

runner = CliRunner()


def test_root_callback_uses_jira_product_config_without_profile(tmp_path: Path, monkeypatch) -> None:
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

    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda context: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "url": context.url}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "jira", "issue", "get", "DEMO-1", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout


def test_root_callback_uses_confluence_product_config_without_profile(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [confluence]
        deployment = "dc"
        url = "https://confluence.example.com"
        auth = "pat"
        token = "wiki-token"
        """.strip()
    )

    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda context: type(
            "FakeService",
            (),
            {"get": lambda self, page_id: {"id": page_id, "url": context.url}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "confluence", "page", "get", "1234", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"url": "https://confluence.example.com"' in result.stdout


def test_root_callback_uses_bitbucket_product_headers_without_profile(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [bitbucket]
        deployment = "dc"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "repo-token"

        [bitbucket.headers]
        accessToken = "$(example-oauth token)"
        """.strip()
    )

    monkeypatch.setattr(header_substitution, "run_header_command", lambda command: "profile-token")

    from atlassian_cli.products.bitbucket.commands import project as project_module

    monkeypatch.setattr(
        project_module,
        "build_project_service",
        lambda context: type(
            "FakeService",
            (),
            {
                "list": lambda self, start, limit: [
                    {
                        "accessToken": context.auth.headers.get("accessToken"),
                        "X-Request-Source": context.auth.headers.get("X-Request-Source"),
                    }
                ]
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--config-file", str(config_file), "bitbucket", "project", "list", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"accessToken": "profile-token"' in result.stdout
    assert '"X-Request-Source": "config-default"' in result.stdout


def test_root_callback_profile_still_uses_legacy_profiles(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [jira]
        deployment = "server"
        url = "https://jira.top-level.example.com"
        auth = "basic"
        username = "top-level"
        token = "top-level-token"

        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.profile.example.com"
        auth = "basic"
        username = "profile-user"
        token = "profile-token"
        """.strip()
    )

    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda context: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "url": context.url}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--profile",
            "prod_jira",
            "jira",
            "issue",
            "get",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.profile.example.com"' in result.stdout


def test_root_callback_reports_created_template_for_missing_product_config(monkeypatch) -> None:
    generated = Path("/tmp/generated-config.toml")
    monkeypatch.setattr(cli_module, "ensure_default_config", lambda path, default_path: True)
    monkeypatch.setattr(cli_module, "load_config", lambda path: LoadedConfig())

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(generated),
            "jira",
            "issue",
            "get",
            "DEMO-1",
        ],
    )

    assert result.exit_code == 2
    assert f"Created {generated}. Fill in [jira] or pass --url." in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_cli_context.py -v`
Expected: FAIL because `cli.py` still falls back to the first profile and does not look up `[jira]`, `[confluence]`, or `[bitbucket]`

- [ ] **Step 3: Write the minimal implementation**

```python
import os
from pathlib import Path

import typer

from atlassian_cli.auth.headers import parse_cli_headers
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import (
    Deployment,
    LoadedConfig,
    Product,
    ProfileConfig,
    RuntimeOverrides,
)
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.config.template import ensure_default_config
from atlassian_cli.core.errors import ConfigError


def _missing_product_message(config_file: Path, product: Product, *, created: bool) -> str:
    if created:
        return f"Created {config_file}. Fill in [{product.value}] or pass --url."
    return f"Fill in [{product.value}] in {config_file} or pass --url."


@app.callback()
def root_callback(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile"),
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, "--config-file"),
    deployment: Deployment | None = typer.Option(None, "--deployment"),
    url: str | None = typer.Option(None, "--url"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "--password"),
    token: str | None = typer.Option(None, "--token"),
    auth: AuthMode | None = typer.Option(None, "--auth"),
    header: list[str] = typer.Option([], "--header"),
    output: str = typer.Option("table", "--output"),
) -> None:
    if ctx.invoked_subcommand is None:
        return

    product = Product(ctx.invoked_subcommand)
    created_template = ensure_default_config(config_file, default_path=DEFAULT_CONFIG_FILE)
    config = load_config(config_file) if config_file.exists() else LoadedConfig()

    try:
        headers = parse_cli_headers(header)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--header") from exc

    if profile:
        selected_profile = config.profiles.get(profile)
        if selected_profile is None:
            raise typer.BadParameter(f"Unknown profile: {profile}", param_hint="--profile")
        base_profile = selected_profile
    elif url is None:
        product_config = config.product_config(product)
        if product_config is None:
            raise typer.BadParameter(_missing_product_message(config_file, product, created=created_template))
        try:
            base_profile = product_config.to_profile_config(product=product, name=product.value)
        except ConfigError as exc:
            raise typer.BadParameter(_missing_product_message(config_file, product, created=created_template)) from exc
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

    ctx.obj = resolve_runtime_context(
        profile=base_profile,
        env=dict(os.environ),
        default_headers=config.headers,
        overrides=RuntimeOverrides(
            profile=profile,
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_cli_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py tests/test_cli_context.py
git commit -m "feat: auto-select product config blocks"
```

## Task 4: Update README and Run Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing doc check**

Run: `rg -n "\[profiles\.|--profile code|\[jira\]|\[confluence\]|\[bitbucket\]|auto-created|optional and mainly for legacy" README.md`
Expected: output shows only legacy `profiles` examples and no explanation of product-block auto-selection

- [ ] **Step 2: Write the documentation update**

````md
## Examples

- `atlassian jira issue get DEMO-1 --output json`
- `atlassian confluence page get 1234 --output json`
- `atlassian bitbucket repo get DEMO example-repo --output json`

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.example.com --header 'accessToken: ...' bitbucket pr list DEMO example-repo --output json`

Config file example:

```toml
[headers]
X-Request-Source = "example-oauth"

[bitbucket]
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"

[bitbucket.headers]
accessToken = "$(example-oauth token)"
```

- `atlassian bitbucket pr list DEMO example-repo --output json`

The default `~/.config/atlassian-cli/config.toml` file is auto-created as a template on first use.
`--profile` remains available for legacy `[profiles.<name>]` compatibility, but top-level `[jira]`, `[confluence]`, and `[bitbucket]` are the primary config shape.
````

- [ ] **Step 3: Run the doc check again**

Run: `rg -n "\[profiles\.|--profile code|\[jira\]|\[confluence\]|\[bitbucket\]|auto-created|optional and mainly for legacy" README.md`
Expected: matches for `[jira]`, `[confluence]`, `[bitbucket]`, and the auto-created template note

- [ ] **Step 4: Run the final verification**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md src/atlassian_cli/config/template.py src/atlassian_cli/config/models.py src/atlassian_cli/config/loader.py src/atlassian_cli/cli.py tests/config/test_template.py tests/config/test_loader.py tests/test_cli_context.py
git commit -m "docs: document product config auto-selection"
```
