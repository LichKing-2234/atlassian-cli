# Atlassian CLI Remove Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove legacy `[profiles.<name>]` config and the `--profile` flag so the CLI only supports top-level `[jira]`, `[confluence]`, `[bitbucket]`, and `[headers]`.

**Architecture:** Keep `ProfileConfig` as an internal normalized runtime shape, but stop parsing persisted profiles and stop exposing `--profile` at the CLI boundary. The loader becomes product-block only, the default template loses all legacy comments, and CLI command resolution always derives its base config from the invoked product block unless inline flags like `--url` are provided.

**Tech Stack:** Python 3.13, Typer, Pydantic, atlassian-python-api, pytest

---

## Planned File Structure

### Modify

- `src/atlassian_cli/config/template.py`
- `src/atlassian_cli/config/models.py`
- `src/atlassian_cli/config/loader.py`
- `src/atlassian_cli/cli.py`
- `tests/config/test_template.py`
- `tests/config/test_loader.py`
- `tests/test_cli_context.py`
- `tests/test_cli_help.py`
- `README.md`

### Responsibility Notes

- `config/template.py` owns the default template content and must remove all legacy `profiles` examples.
- `config/models.py` keeps runtime config types, but `LoadedConfig` no longer stores `profiles`.
- `config/loader.py` parses only `[headers]`, `[jira]`, `[confluence]`, and `[bitbucket]`, and raises `ConfigError` on `profiles`.
- `cli.py` removes `--profile` completely and always selects the product-matching top-level block.
- `tests/test_cli_help.py` becomes the guardrail for the removed flag staying out of help output.

### Common Commands

- Template tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_template.py -v`
- Loader tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_loader.py -v`
- CLI tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_cli_context.py tests/test_cli_help.py -v`
- Full suite: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest -q`

## Task 1: Remove Legacy Profile Examples From the Default Template

**Files:**
- Modify: `src/atlassian_cli/config/template.py`
- Modify: `tests/config/test_template.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from atlassian_cli.config.template import DEFAULT_CONFIG_TEMPLATE, ensure_default_config


def test_ensure_default_config_creates_template_for_default_path(tmp_path: Path) -> None:
    config_file = tmp_path / "atlassian-cli" / "config.toml"

    created = ensure_default_config(config_file, default_path=config_file)

    assert created is True
    assert config_file.read_text() == DEFAULT_CONFIG_TEMPLATE


def test_default_config_template_uses_only_top_level_product_blocks() -> None:
    assert "[jira]" in DEFAULT_CONFIG_TEMPLATE
    assert "[confluence]" in DEFAULT_CONFIG_TEMPLATE
    assert "[bitbucket]" in DEFAULT_CONFIG_TEMPLATE
    assert "[profiles." not in DEFAULT_CONFIG_TEMPLATE
    assert "Legacy compatibility" not in DEFAULT_CONFIG_TEMPLATE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_template.py -v`
Expected: FAIL because the current template still contains legacy `profiles` comments

- [ ] **Step 3: Write the minimal implementation**

```python
from pathlib import Path


DEFAULT_CONFIG_TEMPLATE = """[headers]
# accessToken = "$(example-oauth token)"

[jira]
# deployment = "server"
# url = "https://jira.example.com"
# auth = "basic"
# username = "alice"
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
git commit -m "feat: drop legacy profile template examples"
```

## Task 2: Reject Legacy Profiles in the Loader

**Files:**
- Modify: `src/atlassian_cli/config/models.py`
- Modify: `src/atlassian_cli/config/loader.py`
- Modify: `tests/config/test_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Product, ProductConfig
from atlassian_cli.core.errors import ConfigError


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
        username = "alice"
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


def test_load_config_rejects_legacy_profiles_table(tmp_path: Path) -> None:
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

    with pytest.raises(ConfigError, match="Profile-based config \\[profiles\\.\\*\\] has been removed"):
        load_config(config_file)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_loader.py -v`
Expected: FAIL because the current loader still parses `profiles`

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

from atlassian_cli.config.models import LoadedConfig
from atlassian_cli.core.errors import ConfigError


def load_config(path: Path) -> LoadedConfig:
    data = tomllib.loads(path.read_text())
    if "profiles" in data:
        raise ConfigError(
            "Profile-based config [profiles.*] has been removed. "
            "Migrate to top-level [jira], [confluence], or [bitbucket]."
        )
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

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/config/test_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/models.py src/atlassian_cli/config/loader.py tests/config/test_loader.py
git commit -m "feat: remove profile parsing from config loader"
```

## Task 3: Remove `--profile` and Always Use Product Blocks

**Files:**
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/test_cli_context.py`
- Modify: `tests/test_cli_help.py`

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
        username = "alice"
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
        ["--config-file", str(config_file), "jira", "issue", "get", "OPS-1", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout


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


def test_root_callback_reports_created_template_for_missing_product_config(monkeypatch) -> None:
    generated = Path("/tmp/generated-config.toml")
    monkeypatch.setattr(cli_module, "ensure_default_config", lambda path, default_path: True)
    monkeypatch.setattr(cli_module, "load_config", lambda path: LoadedConfig())

    result = runner.invoke(
        app,
        ["--config-file", str(generated), "jira", "issue", "get", "OPS-1"],
    )

    assert result.exit_code == 2
    assert f"Created {generated}. Fill in [jira] or pass" in result.output
    assert "--url" in result.output


def test_root_help_does_not_show_profile_flag() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--profile" not in result.stdout


def test_root_callback_rejects_removed_profile_flag() -> None:
    result = runner.invoke(app, ["--profile", "prod_jira", "--help"])

    assert result.exit_code == 2
    assert "No such option: --profile" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_cli_context.py tests/test_cli_help.py -v`
Expected: FAIL because `cli.py` still declares `--profile` and still references `config.profiles`

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

    if url is None:
        product_config = config.product_config(product)
        if product_config is None:
            raise typer.BadParameter(
                _missing_product_message(config_file, product, created=created_template)
            )
        try:
            base_profile = product_config.to_profile_config(
                product=product,
                name=product.value,
            )
        except ConfigError as exc:
            raise typer.BadParameter(
                _missing_product_message(config_file, product, created=created_template)
            ) from exc
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

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_cli_context.py tests/test_cli_help.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py tests/test_cli_context.py tests/test_cli_help.py
git commit -m "feat: remove profile flag from cli"
```

## Task 4: Update README and Run Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing doc check**

Run: `rg -n "\\[profiles\\.|--profile|\\[jira\\]|\\[confluence\\]|\\[bitbucket\\]" README.md`
Expected: output still contains `--profile` or old profile phrasing

- [ ] **Step 2: Write the documentation update**

````md
## Examples

- `atlassian jira issue get OPS-1 --output json`
- `atlassian confluence page get 1234 --output json`
- `atlassian bitbucket repo get OPS infra --output json`

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.example.com --header 'accessToken: ...' bitbucket pr list SDK example-repo --output json`

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

- `atlassian bitbucket pr list SDK example-repo --output json`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.
The default `~/.config/atlassian-cli/config.toml` file is auto-created as a template on first use.
Only top-level `[jira]`, `[confluence]`, `[bitbucket]`, and `[headers]` are supported.
```` 

- [ ] **Step 3: Run the doc check again**

Run: `rg -n "\\[profiles\\.|--profile|\\[jira\\]|\\[confluence\\]|\\[bitbucket\\]" README.md`
Expected: matches for `[jira]`, `[confluence]`, and `[bitbucket]`, with no `--profile` or `[profiles.` matches

- [ ] **Step 4: Run the final verification**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md src/atlassian_cli/config/template.py src/atlassian_cli/config/models.py src/atlassian_cli/config/loader.py src/atlassian_cli/cli.py tests/config/test_template.py tests/config/test_loader.py tests/test_cli_context.py tests/test_cli_help.py
git commit -m "docs: document top-level product config only"
```
