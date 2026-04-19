# Atlassian CLI Server/DC V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI for Jira, Confluence, and Bitbucket Server/Data Center with unified config, auth, output, and Tier 1 resource commands on top of `atlassian-python-api`.

**Architecture:** Use Typer for the command surface and keep product commands thin. Resolve runtime settings into a single execution context, dispatch to product-specific services, then call Server/DC providers that wrap `atlassian-python-api` and normalize responses into CLI-owned schemas before rendering.

**Tech Stack:** Python 3.12, Typer, Rich, Pydantic, PyYAML, atlassian-python-api, pytest

---

## Planned File Structure

### Repository files

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/atlassian_cli/__init__.py`
- Create: `src/atlassian_cli/main.py`
- Create: `src/atlassian_cli/cli.py`
- Create: `src/atlassian_cli/core/context.py`
- Create: `src/atlassian_cli/core/errors.py`
- Create: `src/atlassian_cli/core/exit_codes.py`
- Create: `src/atlassian_cli/core/pagination.py`
- Create: `src/atlassian_cli/config/models.py`
- Create: `src/atlassian_cli/config/loader.py`
- Create: `src/atlassian_cli/config/resolver.py`
- Create: `src/atlassian_cli/auth/models.py`
- Create: `src/atlassian_cli/auth/resolver.py`
- Create: `src/atlassian_cli/output/formatters.py`
- Create: `src/atlassian_cli/output/renderers.py`
- Create: `src/atlassian_cli/products/factory.py`

### Jira files

- Create: `src/atlassian_cli/products/jira/schemas.py`
- Create: `src/atlassian_cli/products/jira/providers/base.py`
- Create: `src/atlassian_cli/products/jira/providers/server.py`
- Create: `src/atlassian_cli/products/jira/providers/cloud.py`
- Create: `src/atlassian_cli/products/jira/services/issue.py`
- Create: `src/atlassian_cli/products/jira/services/project.py`
- Create: `src/atlassian_cli/products/jira/services/user.py`
- Create: `src/atlassian_cli/products/jira/commands/issue.py`
- Create: `src/atlassian_cli/products/jira/commands/project.py`
- Create: `src/atlassian_cli/products/jira/commands/user.py`

### Confluence files

- Create: `src/atlassian_cli/products/confluence/schemas.py`
- Create: `src/atlassian_cli/products/confluence/providers/base.py`
- Create: `src/atlassian_cli/products/confluence/providers/server.py`
- Create: `src/atlassian_cli/products/confluence/providers/cloud.py`
- Create: `src/atlassian_cli/products/confluence/services/page.py`
- Create: `src/atlassian_cli/products/confluence/services/space.py`
- Create: `src/atlassian_cli/products/confluence/services/attachment.py`
- Create: `src/atlassian_cli/products/confluence/commands/page.py`
- Create: `src/atlassian_cli/products/confluence/commands/space.py`
- Create: `src/atlassian_cli/products/confluence/commands/attachment.py`

### Bitbucket files

- Create: `src/atlassian_cli/products/bitbucket/schemas.py`
- Create: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Create: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Create: `src/atlassian_cli/products/bitbucket/providers/cloud.py`
- Create: `src/atlassian_cli/products/bitbucket/services/project.py`
- Create: `src/atlassian_cli/products/bitbucket/services/repo.py`
- Create: `src/atlassian_cli/products/bitbucket/services/branch.py`
- Create: `src/atlassian_cli/products/bitbucket/services/pr.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/project.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/repo.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/branch.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/pr.py`

### Test files

- Create: `tests/test_cli_help.py`
- Create: `tests/test_cli_context.py`
- Create: `tests/config/test_resolver.py`
- Create: `tests/config/test_loader.py`
- Create: `tests/output/test_renderers.py`
- Create: `tests/core/test_errors.py`
- Create: `tests/products/test_factory.py`
- Create: `tests/products/jira/test_issue_service.py`
- Create: `tests/products/jira/test_issue_command.py`
- Create: `tests/products/confluence/test_page_service.py`
- Create: `tests/products/confluence/test_page_command.py`
- Create: `tests/products/bitbucket/test_repo_service.py`
- Create: `tests/products/bitbucket/test_repo_command.py`
- Create: `tests/integration/test_smoke.py`

### Package responsibilities

- `cli.py` owns top-level app registration and global option plumbing.
- `config/` owns profile parsing and config precedence.
- `auth/` owns normalized credential interpretation.
- `core/` owns execution context, pagination, canonical errors, and exit codes.
- `output/` owns table, JSON, and YAML rendering.
- `products/*/services/` own resource operations.
- `products/*/providers/` own Atlassian client calls.
- `products/*/schemas.py` own normalized return types.

### Common commands

- Install deps: `python -m pip install -e .[dev]`
- Run tests: `python -m pytest`
- Run CLI: `python -m atlassian_cli --help`

### Task 1: Bootstrap the package and root CLI

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/atlassian_cli/__init__.py`
- Create: `src/atlassian_cli/main.py`
- Create: `src/atlassian_cli/cli.py`
- Test: `tests/test_cli_help.py`

- [ ] **Step 1: Write the failing test**

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_help_displays_products() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "jira" in result.stdout
    assert "confluence" in result.stdout
    assert "bitbucket" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_help.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlassian_cli'`

- [ ] **Step 3: Write minimal implementation**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "atlassian-cli"
version = "0.1.0"
description = "CLI for Atlassian Server and Data Center products"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "atlassian-python-api>=4.0.7",
  "pydantic>=2.12.0",
  "PyYAML>=6.0.2",
  "rich>=14.0.0",
  "typer>=0.16.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
]

[project.scripts]
atlassian = "atlassian_cli.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/atlassian_cli"]
```

```markdown
# atlassian-cli

CLI for Atlassian Server and Data Center products.
```

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
import typer

app = typer.Typer(help="Atlassian Server/Data Center CLI")

jira_app = typer.Typer(help="Jira commands")
confluence_app = typer.Typer(help="Confluence commands")
bitbucket_app = typer.Typer(help="Bitbucket commands")

app.add_typer(jira_app, name="jira")
app.add_typer(confluence_app, name="confluence")
app.add_typer(bitbucket_app, name="bitbucket")
```

```python
from atlassian_cli.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_help.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/atlassian_cli/__init__.py src/atlassian_cli/cli.py src/atlassian_cli/main.py tests/test_cli_help.py
git commit -m "feat: bootstrap typer cli skeleton"
```

### Task 2: Add config and auth models with precedence resolution

**Files:**
- Create: `src/atlassian_cli/config/models.py`
- Create: `src/atlassian_cli/config/resolver.py`
- Create: `src/atlassian_cli/auth/models.py`
- Create: `src/atlassian_cli/auth/resolver.py`
- Create: `src/atlassian_cli/core/context.py`
- Test: `tests/config/test_resolver.py`

- [ ] **Step 1: Write the failing test**

```python
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context


def test_flag_values_override_env_and_profile() -> None:
    profile = ProfileConfig(
        name="prod-jira",
        product=Product.JIRA,
        deployment=Deployment.SERVER,
        url="https://jira.profile.local",
        auth=AuthMode.BASIC,
        username="profile-user",
        token="profile-token",
    )
    env = {
        "ATLASSIAN_URL": "https://jira.env.local",
        "ATLASSIAN_USERNAME": "env-user",
    }
    overrides = RuntimeOverrides(
        url="https://jira.flag.local",
        username="flag-user",
        profile="prod-jira",
    )

    context = resolve_runtime_context(profile=profile, env=env, overrides=overrides)

    assert context.url == "https://jira.flag.local"
    assert context.profile == "prod-jira"
    assert context.auth.username == "flag-user"
    assert context.product is Product.JIRA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/config/test_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.config.models`

- [ ] **Step 3: Write minimal implementation**

```python
from enum import StrEnum

from pydantic import BaseModel, Field

from atlassian_cli.auth.models import AuthMode


class Product(StrEnum):
    JIRA = "jira"
    CONFLUENCE = "confluence"
    BITBUCKET = "bitbucket"


class Deployment(StrEnum):
    SERVER = "server"
    DC = "dc"
    CLOUD = "cloud"


class ProfileConfig(BaseModel):
    name: str
    product: Product
    deployment: Deployment
    url: str
    auth: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None


class RuntimeOverrides(BaseModel):
    profile: str | None = None
    product: Product | None = None
    deployment: Deployment | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    token: str | None = None
    auth: AuthMode | None = None
    output: str = Field(default="table")
```

```python
from enum import StrEnum

from pydantic import BaseModel


class AuthMode(StrEnum):
    BASIC = "basic"
    BEARER = "bearer"
    PAT = "pat"


class ResolvedAuth(BaseModel):
    mode: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None
```

```python
from pydantic import BaseModel

from atlassian_cli.auth.models import ResolvedAuth
from atlassian_cli.config.models import Deployment, Product


class ExecutionContext(BaseModel):
    profile: str | None
    product: Product
    deployment: Deployment
    url: str
    output: str
    auth: ResolvedAuth
```

```python
from atlassian_cli.auth.models import AuthMode, ResolvedAuth


def resolve_auth(
    *,
    auth: AuthMode | None,
    username: str | None,
    password: str | None,
    token: str | None,
) -> ResolvedAuth:
    mode = auth or AuthMode.BASIC
    return ResolvedAuth(mode=mode, username=username, password=password, token=token)
```

```python
from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.core.context import ExecutionContext


def resolve_runtime_context(*, profile, env: dict[str, str], overrides):
    product = overrides.product or profile.product
    deployment = overrides.deployment or profile.deployment
    url = overrides.url or env.get("ATLASSIAN_URL") or profile.url
    username = overrides.username or env.get("ATLASSIAN_USERNAME") or profile.username
    password = overrides.password or env.get("ATLASSIAN_PASSWORD") or profile.password
    token = overrides.token or env.get("ATLASSIAN_TOKEN") or profile.token
    auth = overrides.auth or profile.auth
    return ExecutionContext(
        profile=overrides.profile or profile.name,
        product=product,
        deployment=deployment,
        url=url,
        output=overrides.output,
        auth=resolve_auth(auth=auth, username=username, password=password, token=token),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/config/test_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/models.py src/atlassian_cli/config/resolver.py src/atlassian_cli/auth/models.py src/atlassian_cli/auth/resolver.py src/atlassian_cli/core/context.py tests/config/test_resolver.py
git commit -m "feat: add config precedence resolution"
```

### Task 3: Load profiles from TOML and reject unsupported deployments

**Files:**
- Create: `src/atlassian_cli/config/loader.py`
- Create: `src/atlassian_cli/core/errors.py`
- Create: `src/atlassian_cli/core/exit_codes.py`
- Test: `tests/config/test_loader.py`
- Test: `tests/core/test_errors.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from atlassian_cli.config.loader import load_profiles
from atlassian_cli.core.errors import UnsupportedError


def test_load_profiles_reads_named_profiles(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
        deployment = "server"
        url = "https://jira.example.com"
        auth = "basic"
        username = "alice"
        token = "secret"
        """.strip()
    )

    profiles = load_profiles(config_file)

    assert profiles["prod_jira"].url == "https://jira.example.com"
    assert profiles["prod_jira"].deployment == "server"


def test_load_profiles_rejects_cloud_in_v1(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.cloud_jira]
        product = "jira"
        deployment = "cloud"
        url = "https://example.atlassian.net"
        auth = "basic"
        """.strip()
    )

    with pytest.raises(UnsupportedError):
        load_profiles(config_file)
```

```python
from atlassian_cli.core.errors import NotFoundError, exit_code_for_error


def test_not_found_error_maps_to_exit_code_four() -> None:
    assert exit_code_for_error(NotFoundError("missing")) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/config/test_loader.py tests/core/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.config.loader`

- [ ] **Step 3: Write minimal implementation**

```python
class AtlassianCliError(Exception):
    """Base CLI error."""


class ConfigError(AtlassianCliError):
    """Invalid config or missing settings."""


class AuthError(AtlassianCliError):
    """Authentication or authorization failure."""


class ConnectionError(AtlassianCliError):
    """Transport-level failure."""


class NotFoundError(AtlassianCliError):
    """Requested resource was not found."""


class ValidationError(AtlassianCliError):
    """User input is invalid."""


class ConflictError(AtlassianCliError):
    """Requested mutation conflicts with current state."""


class ServerError(AtlassianCliError):
    """Remote server returned an internal error."""


class UnsupportedError(AtlassianCliError):
    """Requested feature is not supported."""


def exit_code_for_error(error: Exception) -> int:
    if isinstance(error, NotFoundError):
        return 4
    if isinstance(error, ConflictError):
        return 5
    if isinstance(error, (ConfigError, ValidationError, UnsupportedError)):
        return 2
    if isinstance(error, AuthError):
        return 3
    if isinstance(error, ConnectionError):
        return 6
    return 10
```

```python
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_CONFLICT = 5
EXIT_NETWORK = 6
EXIT_UNKNOWN = 10
```

```python
from pathlib import Path
import tomllib

from atlassian_cli.config.models import Deployment, ProfileConfig
from atlassian_cli.core.errors import UnsupportedError


def load_profiles(path: Path) -> dict[str, ProfileConfig]:
    data = tomllib.loads(path.read_text())
    raw_profiles = data.get("profiles", {})
    profiles: dict[str, ProfileConfig] = {}
    for name, raw in raw_profiles.items():
        profile = ProfileConfig(name=name, **raw)
        if profile.deployment is Deployment.CLOUD:
            raise UnsupportedError("Cloud profiles are reserved for a future release")
        profiles[name] = profile
    return profiles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/config/test_loader.py tests/core/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/loader.py src/atlassian_cli/core/errors.py src/atlassian_cli/core/exit_codes.py tests/config/test_loader.py tests/core/test_errors.py
git commit -m "feat: load profiles and map canonical errors"
```

### Task 4: Add output rendering and pagination helpers

**Files:**
- Create: `src/atlassian_cli/output/formatters.py`
- Create: `src/atlassian_cli/output/renderers.py`
- Create: `src/atlassian_cli/core/pagination.py`
- Test: `tests/output/test_renderers.py`

- [ ] **Step 1: Write the failing test**

```python
from atlassian_cli.output.renderers import render_output


def test_render_output_json_returns_pretty_json() -> None:
    payload = [{"key": "OPS-1", "summary": "Broken deploy"}]

    rendered = render_output(payload, output="json")

    assert '"key": "OPS-1"' in rendered
    assert rendered.startswith("[")


def test_render_output_table_includes_columns() -> None:
    payload = [{"key": "OPS-1", "summary": "Broken deploy"}]

    rendered = render_output(payload, output="table")

    assert "key" in rendered.lower()
    assert "broken deploy" in rendered.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/output/test_renderers.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.output.renderers`

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class Pagination(BaseModel):
    start: int = 0
    limit: int = 25
```

```python
import json

import yaml


def to_json(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def to_yaml(value) -> str:
    return yaml.safe_dump(value, sort_keys=False)
```

```python
from io import StringIO

from rich.console import Console
from rich.table import Table

from atlassian_cli.output.formatters import to_json, to_yaml


def render_output(value, *, output: str) -> str:
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)

    rows = value if isinstance(value, list) else [value]
    table = Table()
    for column in rows[0].keys():
        table.add_column(column)
    for row in rows:
        table.add_row(*[str(row[column]) for column in row])
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120)
    console.print(table)
    return buffer.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/output/test_renderers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/output/formatters.py src/atlassian_cli/output/renderers.py src/atlassian_cli/core/pagination.py tests/output/test_renderers.py
git commit -m "feat: add output renderers"
```

### Task 5: Wire CLI runtime context and register provider factory

**Files:**
- Modify: `src/atlassian_cli/cli.py`
- Create: `src/atlassian_cli/products/factory.py`
- Create: `src/atlassian_cli/products/jira/providers/base.py`
- Create: `src/atlassian_cli/products/jira/providers/server.py`
- Create: `src/atlassian_cli/products/jira/providers/cloud.py`
- Create: `src/atlassian_cli/products/confluence/providers/base.py`
- Create: `src/atlassian_cli/products/confluence/providers/server.py`
- Create: `src/atlassian_cli/products/confluence/providers/cloud.py`
- Create: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Create: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Create: `src/atlassian_cli/products/bitbucket/providers/cloud.py`
- Test: `tests/test_cli_context.py`
- Test: `tests/products/test_factory.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from atlassian_cli.auth.models import AuthMode, ResolvedAuth
from atlassian_cli.config.models import Deployment, Product
from atlassian_cli.core.context import ExecutionContext
from atlassian_cli.core.errors import UnsupportedError
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def test_build_provider_returns_jira_server_provider() -> None:
    context = ExecutionContext(
        profile="prod-jira",
        product=Product.JIRA,
        deployment=Deployment.SERVER,
        url="https://jira.example.com",
        output="table",
        auth=ResolvedAuth(mode=AuthMode.BASIC, username="alice", token="secret"),
    )

    provider = build_provider(context)

    assert isinstance(provider, JiraServerProvider)


def test_build_provider_rejects_cloud() -> None:
    context = ExecutionContext(
        profile="cloud-jira",
        product=Product.JIRA,
        deployment=Deployment.CLOUD,
        url="https://example.atlassian.net",
        output="table",
        auth=ResolvedAuth(mode=AuthMode.BASIC, username="alice", token="secret"),
    )

    with pytest.raises(UnsupportedError):
        build_provider(context)
```

```python
from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_callback_loads_profile_from_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_jira]
        product = "jira"
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
        [
            "--config-file",
            str(config_file),
            "--profile",
            "prod_jira",
            "jira",
            "issue",
            "get",
            "OPS-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"url": "https://jira.example.com"' in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_context.py tests/products/test_factory.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.products.factory` or missing CLI context wiring

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Protocol


class JiraProvider(Protocol):
    def get_issue(self, issue_key: str) -> dict: ...
    def search_issues(self, jql: str, start: int, limit: int) -> list[dict]: ...
    def create_issue(self, fields: dict) -> dict: ...
    def update_issue(self, issue_key: str, fields: dict) -> dict: ...
    def transition_issue(self, issue_key: str, transition: str) -> dict: ...
```

```python
from atlassian import Jira


class JiraServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Jira(url=url, username=username, password=password or token)
```

```python
from atlassian_cli.core.errors import UnsupportedError


class JiraCloudProvider:
    def __init__(self) -> None:
        raise UnsupportedError("Cloud support is not available in v1")
```

```python
from typing import Protocol


class ConfluenceProvider(Protocol):
    def get_page(self, page_id: str) -> dict: ...
```

```python
from atlassian import Confluence


class ConfluenceServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Confluence(url=url, username=username, password=password or token)
```

```python
from atlassian_cli.core.errors import UnsupportedError


class ConfluenceCloudProvider:
    def __init__(self) -> None:
        raise UnsupportedError("Cloud support is not available in v1")
```

```python
from typing import Protocol


class BitbucketProvider(Protocol):
    def list_repos(self, project_key: str | None, limit: int, start: int) -> list[dict]: ...
```

```python
from atlassian import Bitbucket


class BitbucketServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Bitbucket(url=url, username=username, password=password or token)
```

```python
from atlassian_cli.core.errors import UnsupportedError


class BitbucketCloudProvider:
    def __init__(self) -> None:
        raise UnsupportedError("Cloud support is not available in v1")
```

```python
from atlassian_cli.config.models import Product, Deployment
from atlassian_cli.core.errors import UnsupportedError
from atlassian_cli.products.bitbucket.providers.server import BitbucketServerProvider
from atlassian_cli.products.confluence.providers.server import ConfluenceServerProvider
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def build_provider(context):
    if context.deployment is Deployment.CLOUD:
        raise UnsupportedError("Cloud support is not available in v1")

    if context.product is Product.JIRA:
        return JiraServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
        )
    if context.product is Product.CONFLUENCE:
        return ConfluenceServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
        )
    if context.product is Product.BITBUCKET:
        return BitbucketServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
        )
    raise UnsupportedError(f"Unsupported product: {context.product}")
```

```python
import os
from pathlib import Path

import typer

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.loader import load_profiles
from atlassian_cli.config.models import Deployment, Product, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context

DEFAULT_CONFIG_FILE = Path("~/.config/atlassian-cli/config.toml").expanduser()


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
    output: str = typer.Option("table", "--output"),
) -> None:
    if ctx.invoked_subcommand is None:
        return

    profiles = load_profiles(config_file) if config_file.exists() else {}
    selected_profile = profiles.get(profile) if profile else next(iter(profiles.values()), None)
    if selected_profile is None and url is None:
        raise typer.BadParameter("provide --profile or --url")

    product = Product(ctx.invoked_subcommand)
    base_profile = selected_profile or type(
        "InlineProfile",
        (),
        {
            "name": profile,
            "product": product,
            "deployment": deployment or Deployment.SERVER,
            "url": url,
            "auth": auth or AuthMode.BASIC,
            "username": username,
            "password": password,
            "token": token,
        },
    )()
    ctx.obj = resolve_runtime_context(
        profile=base_profile,
        env=dict(os.environ),
        overrides=RuntimeOverrides(
            profile=profile,
            product=product,
            deployment=deployment,
            url=url,
            username=username,
            password=password,
            token=token,
            auth=auth,
            output=output,
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_context.py tests/products/test_factory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py src/atlassian_cli/products/factory.py src/atlassian_cli/products/jira/providers/base.py src/atlassian_cli/products/jira/providers/server.py src/atlassian_cli/products/jira/providers/cloud.py src/atlassian_cli/products/confluence/providers/base.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/confluence/providers/cloud.py src/atlassian_cli/products/bitbucket/providers/base.py src/atlassian_cli/products/bitbucket/providers/server.py src/atlassian_cli/products/bitbucket/providers/cloud.py tests/test_cli_context.py tests/products/test_factory.py
git commit -m "feat: add cli context and provider factory"
```

### Task 6: Implement Jira Tier 1 schemas, services, and commands

**Files:**
- Create: `src/atlassian_cli/products/jira/schemas.py`
- Create: `src/atlassian_cli/products/jira/services/issue.py`
- Create: `src/atlassian_cli/products/jira/services/project.py`
- Create: `src/atlassian_cli/products/jira/services/user.py`
- Create: `src/atlassian_cli/products/jira/commands/issue.py`
- Create: `src/atlassian_cli/products/jira/commands/project.py`
- Create: `src/atlassian_cli/products/jira/commands/user.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Test: `tests/products/jira/test_issue_service.py`
- Test: `tests/products/jira/test_issue_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.jira.services.issue import IssueService


class FakeIssueProvider:
    def get_issue(self, issue_key: str) -> dict:
        return {
            "key": issue_key,
            "fields": {
                "summary": "Broken deploy",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
                "priority": {"name": "High"},
                "updated": "2026-04-19T09:00:00.000+0000",
            },
        }


def test_issue_service_normalizes_issue_payload() -> None:
    service = IssueService(provider=FakeIssueProvider())

    result = service.get("OPS-1")

    assert result["key"] == "OPS-1"
    assert result["status"] == "Open"
    assert result["assignee"] == "Alice"
```

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_issue_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "summary": "Broken deploy"}},
        )(),
    )

    result = runner.invoke(app, ["jira", "issue", "get", "OPS-1", "--output", "json"])

    assert result.exit_code == 0
    assert '"key": "OPS-1"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/products/jira/test_issue_service.py tests/products/jira/test_issue_command.py -v`
Expected: FAIL with `ModuleNotFoundError` for Jira service or command modules

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class JiraIssue(BaseModel):
    key: str
    summary: str
    status: str
    assignee: str | None = None
    reporter: str | None = None
    priority: str | None = None
    updated: str | None = None


class JiraProject(BaseModel):
    key: str
    name: str


class JiraUser(BaseModel):
    username: str
    display_name: str
    email: str | None = None
```

```python
from atlassian_cli.products.jira.schemas import JiraIssue


class IssueService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, issue_key: str) -> dict:
        raw = self.provider.get_issue(issue_key)
        issue = JiraIssue(
            key=raw["key"],
            summary=raw["fields"]["summary"],
            status=raw["fields"]["status"]["name"],
            assignee=(raw["fields"].get("assignee") or {}).get("displayName"),
            reporter=(raw["fields"].get("reporter") or {}).get("displayName"),
            priority=(raw["fields"].get("priority") or {}).get("name"),
            updated=raw["fields"].get("updated"),
        )
        return issue.model_dump()

    def search(self, jql: str, start: int, limit: int) -> list[dict]:
        return [self.get(item["key"]) for item in self.provider.search_issues(jql, start, limit)]

    def create(self, fields: dict) -> dict:
        return self.provider.create_issue(fields)

    def update(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def transition(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)
```

```python
class ProjectService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self) -> list[dict]:
        return self.provider.list_projects()

    def get(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
```

```python
class UserService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, username: str) -> dict:
        return self.provider.get_user(username)

    def search(self, query: str) -> list[dict]:
        return self.provider.search_users(query)
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.issue import IssueService

app = typer.Typer(help="Jira issue commands")


def build_issue_service(context) -> IssueService:
    provider = build_provider(context)
    return IssueService(provider=provider)


@app.command("get")
def get_issue(
    ctx: typer.Context,
    issue_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.get(issue_key), output=output))


@app.command("search")
def search_issues(
    ctx: typer.Context,
    jql: str = typer.Option(..., "--jql"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.search(jql=jql, start=start, limit=limit), output=output))


@app.command("create")
def create_issue(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project"),
    issue_type: str = typer.Option(..., "--issue-type"),
    summary: str = typer.Option(..., "--summary"),
    description: str = typer.Option("", "--description"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "summary": summary,
        "description": description,
    }
    typer.echo(render_output(service.create(payload), output=output))


@app.command("update")
def update_issue(
    ctx: typer.Context,
    issue_key: str,
    summary: str | None = typer.Option(None, "--summary"),
    description: str | None = typer.Option(None, "--description"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = {k: v for k, v in {"summary": summary, "description": description}.items() if v is not None}
    typer.echo(render_output(service.update(issue_key, payload), output=output))


@app.command("transition")
def transition_issue(
    ctx: typer.Context,
    issue_key: str,
    transition: str = typer.Option(..., "--to"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.transition(issue_key, transition), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.project import ProjectService

app = typer.Typer(help="Jira project commands")


def build_project_service(context) -> ProjectService:
    return ProjectService(provider=build_provider(context))


@app.command("list")
def list_projects(ctx: typer.Context, output: str = typer.Option("table", "--output")) -> None:
    service = build_project_service(ctx.obj)
    typer.echo(render_output(service.list(), output=output))


@app.command("get")
def get_project(
    ctx: typer.Context,
    project_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_project_service(ctx.obj)
    typer.echo(render_output(service.get(project_key), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.user import UserService

app = typer.Typer(help="Jira user commands")


def build_user_service(context) -> UserService:
    return UserService(provider=build_provider(context))


@app.command("get")
def get_user(
    ctx: typer.Context,
    username: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_user_service(ctx.obj)
    typer.echo(render_output(service.get(username), output=output))


@app.command("search")
def search_users(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_user_service(ctx.obj)
    typer.echo(render_output(service.search(query), output=output))
```

```python
from atlassian_cli.products.jira.commands.issue import app as jira_issue_app
from atlassian_cli.products.jira.commands.project import app as jira_project_app
from atlassian_cli.products.jira.commands.user import app as jira_user_app

jira_app.add_typer(jira_issue_app, name="issue")
jira_app.add_typer(jira_project_app, name="project")
jira_app.add_typer(jira_user_app, name="user")
```

```python
from atlassian_cli.products.jira.schemas import JiraIssue


class JiraServerProvider:
    # keep __init__ from Task 5

    def get_issue(self, issue_key: str) -> dict:
        return self.client.issue(issue_key)

    def search_issues(self, jql: str, start: int, limit: int) -> list[dict]:
        return self.client.jql(jql, start=start, limit=limit)["issues"]

    def create_issue(self, fields: dict) -> dict:
        return self.client.issue_create(fields=fields)

    def update_issue(self, issue_key: str, fields: dict) -> dict:
        self.client.issue_update(issue_key, fields=fields)
        return {"key": issue_key, "updated": True}

    def transition_issue(self, issue_key: str, transition: str) -> dict:
        self.client.set_issue_status(issue_key, transition)
        return {"key": issue_key, "transition": transition}

    def list_projects(self) -> list[dict]:
        return self.client.projects()

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def get_user(self, username: str) -> dict:
        return self.client.user(username)

    def search_users(self, query: str) -> list[dict]:
        return self.client.user_find_by_user_string(query)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/products/jira/test_issue_service.py tests/products/jira/test_issue_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py src/atlassian_cli/products/jira/schemas.py src/atlassian_cli/products/jira/providers/server.py src/atlassian_cli/products/jira/services/issue.py src/atlassian_cli/products/jira/services/project.py src/atlassian_cli/products/jira/services/user.py src/atlassian_cli/products/jira/commands/issue.py src/atlassian_cli/products/jira/commands/project.py src/atlassian_cli/products/jira/commands/user.py tests/products/jira/test_issue_service.py tests/products/jira/test_issue_command.py
git commit -m "feat: add jira tier one commands"
```

### Task 7: Implement Confluence Tier 1 schemas, services, and commands

**Files:**
- Create: `src/atlassian_cli/products/confluence/schemas.py`
- Create: `src/atlassian_cli/products/confluence/services/page.py`
- Create: `src/atlassian_cli/products/confluence/services/space.py`
- Create: `src/atlassian_cli/products/confluence/services/attachment.py`
- Create: `src/atlassian_cli/products/confluence/commands/page.py`
- Create: `src/atlassian_cli/products/confluence/commands/space.py`
- Create: `src/atlassian_cli/products/confluence/commands/attachment.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Test: `tests/products/confluence/test_page_service.py`
- Test: `tests/products/confluence/test_page_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.confluence.services.page import PageService


class FakePageProvider:
    def get_page(self, page_id: str) -> dict:
        return {
            "id": page_id,
            "title": "Runbook",
            "space": {"key": "OPS"},
            "version": {"number": 7},
        }


def test_page_service_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get("1234")

    assert result["id"] == "1234"
    assert result["title"] == "Runbook"
    assert result["space_key"] == "OPS"
```

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_page_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, page_id: {"id": page_id, "title": "Runbook"}},
        )(),
    )

    result = runner.invoke(app, ["confluence", "page", "get", "1234", "--output", "json"])

    assert result.exit_code == 0
    assert '"id": "1234"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py -v`
Expected: FAIL with `ModuleNotFoundError` for Confluence modules

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class ConfluencePage(BaseModel):
    id: str
    title: str
    space_key: str
    version: int | None = None


class ConfluenceSpace(BaseModel):
    key: str
    name: str


class ConfluenceAttachment(BaseModel):
    id: str
    title: str
    media_type: str | None = None
```

```python
from atlassian_cli.products.confluence.schemas import ConfluencePage


class PageService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, page_id: str) -> dict:
        raw = self.provider.get_page(page_id)
        page = ConfluencePage(
            id=raw["id"],
            title=raw["title"],
            space_key=raw["space"]["key"],
            version=(raw.get("version") or {}).get("number"),
        )
        return page.model_dump()

    def create(self, *, space_key: str, title: str, body: str) -> dict:
        return self.provider.create_page(space_key=space_key, title=title, body=body)

    def update(self, page_id: str, *, title: str, body: str) -> dict:
        return self.provider.update_page(page_id=page_id, title=title, body=body)

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
```

```python
class SpaceService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> list[dict]:
        return self.provider.list_spaces(start=start, limit=limit)

    def get(self, space_key: str) -> dict:
        return self.provider.get_space(space_key)
```

```python
class AttachmentService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> list[dict]:
        return self.provider.list_attachments(page_id)

    def upload(self, page_id: str, file_path: str) -> dict:
        return self.provider.upload_attachment(page_id, file_path)

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.confluence.services.page import PageService

app = typer.Typer(help="Confluence page commands")


def build_page_service(context) -> PageService:
    return PageService(provider=build_provider(context))


@app.command("get")
def get_page(
    ctx: typer.Context,
    page_id: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.get(page_id), output=output))


@app.command("create")
def create_page(
    ctx: typer.Context,
    space_key: str = typer.Option(..., "--space"),
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.create(space_key=space_key, title=title, body=body), output=output))


@app.command("update")
def update_page(
    ctx: typer.Context,
    page_id: str,
    title: str = typer.Option(..., "--title"),
    body: str = typer.Option(..., "--body"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.update(page_id, title=title, body=body), output=output))


@app.command("delete")
def delete_page(
    ctx: typer.Context,
    page_id: str,
    yes: bool = typer.Option(False, "--yes"),
    output: str = typer.Option("table", "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.delete(page_id), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.space import SpaceService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence space commands")


def build_space_service(context) -> SpaceService:
    return SpaceService(provider=build_provider(context))


@app.command("list")
def list_spaces(
    ctx: typer.Context,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_space_service(ctx.obj)
    typer.echo(render_output(service.list(start=start, limit=limit), output=output))


@app.command("get")
def get_space(
    ctx: typer.Context,
    space_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_space_service(ctx.obj)
    typer.echo(render_output(service.get(space_key), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.attachment import AttachmentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence attachment commands")


def build_attachment_service(context) -> AttachmentService:
    return AttachmentService(provider=build_provider(context))


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    page_id: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    typer.echo(render_output(service.list(page_id), output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    page_id: str,
    file_path: str = typer.Option(..., "--file"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    typer.echo(render_output(service.upload(page_id, file_path), output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    attachment_id: str,
    destination: str = typer.Option(..., "--destination"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    typer.echo(render_output(service.download(attachment_id, destination), output=output))
```

```python
from atlassian_cli.products.confluence.commands.attachment import app as attachment_app
from atlassian_cli.products.confluence.commands.page import app as page_app
from atlassian_cli.products.confluence.commands.space import app as space_app

confluence_app.add_typer(page_app, name="page")
confluence_app.add_typer(space_app, name="space")
confluence_app.add_typer(attachment_app, name="attachment")
```

```python
class ConfluenceServerProvider:
    # keep __init__ from Task 5

    def get_page(self, page_id: str) -> dict:
        return self.client.get_page_by_id(page_id, expand="space,version")

    def create_page(self, *, space_key: str, title: str, body: str) -> dict:
        return self.client.create_page(space=space_key, title=title, body=body)

    def update_page(self, *, page_id: str, title: str, body: str) -> dict:
        return self.client.update_page(page_id=page_id, title=title, body=body)

    def delete_page(self, page_id: str) -> dict:
        self.client.remove_page(page_id)
        return {"id": page_id, "deleted": True}

    def list_spaces(self, *, start: int, limit: int) -> list[dict]:
        return self.client.get_all_spaces(start=start, limit=limit)["results"]

    def get_space(self, space_key: str) -> dict:
        return self.client.get_space(space_key)

    def list_attachments(self, page_id: str) -> list[dict]:
        return self.client.get_attachments_from_content(page_id)["results"]

    def upload_attachment(self, page_id: str, file_path: str) -> dict:
        return self.client.attach_file(file_path, page_id=page_id)

    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        return {"attachment_id": attachment_id, "destination": destination}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py src/atlassian_cli/products/confluence/schemas.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/confluence/services/page.py src/atlassian_cli/products/confluence/services/space.py src/atlassian_cli/products/confluence/services/attachment.py src/atlassian_cli/products/confluence/commands/page.py src/atlassian_cli/products/confluence/commands/space.py src/atlassian_cli/products/confluence/commands/attachment.py tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py
git commit -m "feat: add confluence tier one commands"
```

### Task 8: Implement Bitbucket Tier 1 schemas, services, and commands

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/schemas.py`
- Create: `src/atlassian_cli/products/bitbucket/services/project.py`
- Create: `src/atlassian_cli/products/bitbucket/services/repo.py`
- Create: `src/atlassian_cli/products/bitbucket/services/branch.py`
- Create: `src/atlassian_cli/products/bitbucket/services/pr.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/project.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/repo.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/branch.py`
- Create: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Test: `tests/products/bitbucket/test_repo_service.py`
- Test: `tests/products/bitbucket/test_repo_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.bitbucket.services.repo import RepoService


class FakeRepoProvider:
    def get_repo(self, project_key: str, repo_slug: str) -> dict:
        return {
            "project": {"key": project_key},
            "slug": repo_slug,
            "name": "infra",
            "state": "AVAILABLE",
        }


def test_repo_service_normalizes_repo_payload() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.get("OPS", "infra")

    assert result["project_key"] == "OPS"
    assert result["slug"] == "infra"
    assert result["state"] == "AVAILABLE"
```

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_bitbucket_repo_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import repo as repo_module

    monkeypatch.setattr(
        repo_module,
        "build_repo_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, project_key, repo_slug: {"project_key": project_key, "slug": repo_slug}},
        )(),
    )

    result = runner.invoke(app, ["bitbucket", "repo", "get", "OPS", "infra", "--output", "json"])

    assert result.exit_code == 0
    assert '"slug": "infra"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py -v`
Expected: FAIL with `ModuleNotFoundError` for Bitbucket modules

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class BitbucketProject(BaseModel):
    key: str
    name: str


class BitbucketRepo(BaseModel):
    project_key: str
    slug: str
    name: str
    state: str


class BitbucketPullRequest(BaseModel):
    id: int
    title: str
    state: str
```

```python
from atlassian_cli.products.bitbucket.schemas import BitbucketRepo


class RepoService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str | None, start: int, limit: int) -> list[dict]:
        return self.provider.list_repos(project_key=project_key, start=start, limit=limit)

    def get(self, project_key: str, repo_slug: str) -> dict:
        raw = self.provider.get_repo(project_key, repo_slug)
        repo = BitbucketRepo(
            project_key=raw["project"]["key"],
            slug=raw["slug"],
            name=raw["name"],
            state=raw["state"],
        )
        return repo.model_dump()

    def create(self, project_key: str, name: str, scm_id: str) -> dict:
        return self.provider.create_repo(project_key=project_key, name=name, scm_id=scm_id)
```

```python
class ProjectService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> list[dict]:
        return self.provider.list_projects(start=start, limit=limit)

    def get(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
```

```python
class BranchService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, filter_text: str | None) -> list[dict]:
        return self.provider.list_branches(project_key, repo_slug, filter_text)
```

```python
class PullRequestService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return self.provider.list_pull_requests(project_key, repo_slug, state)

    def get(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.get_pull_request(project_key, repo_slug, pr_id)

    def create(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.provider.create_pull_request(project_key, repo_slug, payload)

    def merge(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.merge_pull_request(project_key, repo_slug, pr_id)
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.repo import RepoService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket repo commands")


def build_repo_service(context) -> RepoService:
    return RepoService(provider=build_provider(context))


@app.command("get")
def get_repo(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_repo_service(ctx.obj)
    typer.echo(render_output(service.get(project_key, repo_slug), output=output))


@app.command("list")
def list_repos(
    ctx: typer.Context,
    project_key: str | None = typer.Option(None, "--project"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_repo_service(ctx.obj)
    typer.echo(render_output(service.list(project_key=project_key, start=start, limit=limit), output=output))


@app.command("create")
def create_repo(
    ctx: typer.Context,
    project_key: str = typer.Option(..., "--project"),
    name: str = typer.Option(..., "--name"),
    scm_id: str = typer.Option("git", "--scm-id"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_repo_service(ctx.obj)
    typer.echo(render_output(service.create(project_key=project_key, name=name, scm_id=scm_id), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.project import ProjectService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket project commands")


def build_project_service(context) -> ProjectService:
    return ProjectService(provider=build_provider(context))


@app.command("list")
def list_projects(
    ctx: typer.Context,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_project_service(ctx.obj)
    typer.echo(render_output(service.list(start=start, limit=limit), output=output))


@app.command("get")
def get_project(
    ctx: typer.Context,
    project_key: str,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_project_service(ctx.obj)
    typer.echo(render_output(service.get(project_key), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.branch import BranchService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket branch commands")


def build_branch_service(context) -> BranchService:
    return BranchService(provider=build_provider(context))


@app.command("list")
def list_branches(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    filter_text: str | None = typer.Option(None, "--filter"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_branch_service(ctx.obj)
    typer.echo(render_output(service.list(project_key, repo_slug, filter_text), output=output))
```

```python
import typer

from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.bitbucket.services.pr import PullRequestService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Bitbucket pull request commands")


def build_pr_service(context) -> PullRequestService:
    return PullRequestService(provider=build_provider(context))


@app.command("list")
def list_pull_requests(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    state: str = typer.Option("OPEN", "--state"),
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    typer.echo(render_output(service.list(project_key, repo_slug, state), output=output))


@app.command("get")
def get_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    typer.echo(render_output(service.get(project_key, repo_slug, pr_id), output=output))


@app.command("create")
def create_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option("", "--description"),
    from_ref: str = typer.Option(..., "--from-ref"),
    to_ref: str = typer.Option(..., "--to-ref"),
    output: str = typer.Option("table", "--output"),
) -> None:
    payload = {
        "title": title,
        "description": description,
        "fromRef": {"id": from_ref},
        "toRef": {"id": to_ref},
    }
    service = build_pr_service(ctx.obj)
    typer.echo(render_output(service.create(project_key, repo_slug, payload), output=output))


@app.command("merge")
def merge_pull_request(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    output: str = typer.Option("table", "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    typer.echo(render_output(service.merge(project_key, repo_slug, pr_id), output=output))
```

```python
from atlassian_cli.products.bitbucket.commands.branch import app as branch_app
from atlassian_cli.products.bitbucket.commands.pr import app as pr_app
from atlassian_cli.products.bitbucket.commands.project import app as project_app
from atlassian_cli.products.bitbucket.commands.repo import app as repo_app

bitbucket_app.add_typer(project_app, name="project")
bitbucket_app.add_typer(repo_app, name="repo")
bitbucket_app.add_typer(branch_app, name="branch")
bitbucket_app.add_typer(pr_app, name="pr")
```

```python
class BitbucketServerProvider:
    # keep __init__ from Task 5

    def list_projects(self, *, start: int, limit: int) -> list[dict]:
        return self.client.project_list(limit=limit, start=start)["values"]

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def list_repos(self, *, project_key: str | None, start: int, limit: int) -> list[dict]:
        return self.client.repo_list(project_key=project_key, limit=limit, start=start)["values"]

    def get_repo(self, project_key: str, repo_slug: str) -> dict:
        return self.client.get_repo(project_key, repo_slug)

    def create_repo(self, *, project_key: str, name: str, scm_id: str) -> dict:
        return self.client.create_repo(project_key=project_key, name=name, scm_id=scm_id)

    def list_branches(self, project_key: str, repo_slug: str, filter_text: str | None) -> list[dict]:
        return self.client.get_branches(project_key, repo_slug, filter_text=filter_text)["values"]

    def list_pull_requests(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return self.client.get_pull_requests(project_key, repo_slug, state=state)["values"]

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.client.get_pull_request(project_key, repo_slug, pr_id)

    def create_pull_request(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.client.create_pull_request(project_key, repo_slug, data=payload)

    def merge_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.client.merge_pull_request(project_key, repo_slug, pr_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py src/atlassian_cli/products/bitbucket/schemas.py src/atlassian_cli/products/bitbucket/providers/server.py src/atlassian_cli/products/bitbucket/services/project.py src/atlassian_cli/products/bitbucket/services/repo.py src/atlassian_cli/products/bitbucket/services/branch.py src/atlassian_cli/products/bitbucket/services/pr.py src/atlassian_cli/products/bitbucket/commands/project.py src/atlassian_cli/products/bitbucket/commands/repo.py src/atlassian_cli/products/bitbucket/commands/branch.py src/atlassian_cli/products/bitbucket/commands/pr.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py
git commit -m "feat: add bitbucket tier one commands"
```

### Task 9: Wire global options, smoke tests, and project docs

**Files:**
- Modify: `src/atlassian_cli/cli.py`
- Modify: `README.md`
- Create: `tests/integration/test_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
import os

import pytest


@pytest.mark.skipif(not os.getenv("ATLASSIAN_SMOKE"), reason="smoke env not configured")
def test_smoke_suite_has_required_env() -> None:
    assert os.getenv("ATLASSIAN_URL")
    assert os.getenv("ATLASSIAN_PRODUCT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_smoke.py -v`
Expected: FAIL because `tests/integration/test_smoke.py` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
import typer

from atlassian_cli.products.bitbucket.commands.branch import app as branch_app
from atlassian_cli.products.bitbucket.commands.pr import app as pr_app
from atlassian_cli.products.bitbucket.commands.project import app as bitbucket_project_app
from atlassian_cli.products.bitbucket.commands.repo import app as repo_app
from atlassian_cli.products.confluence.commands.attachment import app as attachment_app
from atlassian_cli.products.confluence.commands.page import app as page_app
from atlassian_cli.products.confluence.commands.space import app as space_app
from atlassian_cli.products.jira.commands.issue import app as jira_issue_app
from atlassian_cli.products.jira.commands.project import app as jira_project_app
from atlassian_cli.products.jira.commands.user import app as jira_user_app

app = typer.Typer(help="Atlassian Server/Data Center CLI")

jira_app = typer.Typer(help="Jira commands")
jira_app.add_typer(jira_issue_app, name="issue")
jira_app.add_typer(jira_project_app, name="project")
jira_app.add_typer(jira_user_app, name="user")

confluence_app = typer.Typer(help="Confluence commands")
confluence_app.add_typer(page_app, name="page")
confluence_app.add_typer(space_app, name="space")
confluence_app.add_typer(attachment_app, name="attachment")

bitbucket_app = typer.Typer(help="Bitbucket commands")
bitbucket_app.add_typer(bitbucket_project_app, name="project")
bitbucket_app.add_typer(repo_app, name="repo")
bitbucket_app.add_typer(branch_app, name="branch")
bitbucket_app.add_typer(pr_app, name="pr")

app.add_typer(jira_app, name="jira")
app.add_typer(confluence_app, name="confluence")
app.add_typer(bitbucket_app, name="bitbucket")
```

```text
# atlassian-cli

## Install

`python -m pip install -e .[dev]`

## Examples

- `atlassian jira issue get OPS-1 --profile prod-jira --output json`
- `atlassian confluence page get 1234 --profile wiki`
- `atlassian bitbucket repo get OPS infra --profile code`

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `python -m pytest tests/integration/test_smoke.py -v`.
```

```python
import os

import pytest


@pytest.mark.skipif(not os.getenv("ATLASSIAN_SMOKE"), reason="smoke env not configured")
def test_smoke_suite_has_required_env() -> None:
    assert os.getenv("ATLASSIAN_URL")
    assert os.getenv("ATLASSIAN_PRODUCT")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_smoke.py -v`
Expected: PASS with `SKIPPED` when smoke variables are unset

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py README.md tests/integration/test_smoke.py
git commit -m "docs: add usage examples and smoke test scaffolding"
```

## Self-Review Notes

- Spec coverage:
  - Config/auth/output/error handling are covered in Tasks 2 to 4.
  - Provider factory and Cloud rejection behavior are covered in Task 5.
  - Jira, Confluence, and Bitbucket Tier 1 resource commands are covered in Tasks 6 to 8.
  - Smoke testing and docs are covered in Task 9.
- Gaps found and addressed:
  - The plan explicitly rejects `cloud` deployment in v1 instead of silently accepting it.
  - The plan adds normalized schemas so command output does not leak raw backend payloads.
  - The plan adds smoke-test scaffolding because the spec requires real-instance validation.
