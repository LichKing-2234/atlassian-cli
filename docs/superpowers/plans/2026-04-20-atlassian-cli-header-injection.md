# Atlassian CLI Header Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add non-invasive HTTP header injection to the CLI so external tools such as Agora OAuth can provide authenticated request headers without embedding OAuth logic in the CLI.

**Architecture:** Keep OAuth entirely outside the CLI. Extend runtime auth resolution so repeated `--header 'Name: value'` flags and a single `ATLASSIAN_HEADER` environment variable are merged into a resolved header map, then patch those headers onto the underlying `requests.Session` used by the Jira, Confluence, and Bitbucket clients.

**Tech Stack:** Python 3.13, Typer, Pydantic, atlassian-python-api, pytest

---

## Planned File Structure

### Modify

- `src/atlassian_cli/auth/models.py`
- `src/atlassian_cli/auth/resolver.py`
- `src/atlassian_cli/config/models.py`
- `src/atlassian_cli/config/resolver.py`
- `src/atlassian_cli/cli.py`
- `src/atlassian_cli/products/jira/providers/server.py`
- `src/atlassian_cli/products/confluence/providers/server.py`
- `src/atlassian_cli/products/bitbucket/providers/server.py`
- `README.md`

### Create

- `src/atlassian_cli/auth/headers.py`
- `tests/auth/test_headers.py`
- `tests/products/test_header_providers.py`

### Existing tests to extend

- `tests/config/test_resolver.py`
- `tests/test_cli_context.py`

### Responsibility notes

- `auth/headers.py` owns parsing repeated CLI headers and the single `ATLASSIAN_HEADER` environment variable.
- `auth/models.py` and `auth/resolver.py` own normalized header-aware auth state.
- `config/resolver.py` owns precedence merging across flags, env, and profiles.
- `cli.py` only gathers raw CLI options and hands them to the resolver.
- `products/*/providers/server.py` construct SDK clients normally, then patch injected headers onto the underlying session.

### Common commands

- Run focused tests: `.venv/bin/python -m pytest <path> -v`
- Run full suite: `.venv/bin/python -m pytest -q`
- Run CLI help: `.venv/bin/atlassian --help`

### Task 1: Add header parsing primitives and header-aware auth models

**Files:**
- Create: `src/atlassian_cli/auth/headers.py`
- Modify: `src/atlassian_cli/auth/models.py`
- Modify: `src/atlassian_cli/auth/resolver.py`
- Create: `tests/auth/test_headers.py`

- [ ] **Step 1: Write the failing test**

```python
from atlassian_cli.auth.headers import collect_env_headers, parse_cli_headers
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.auth.resolver import resolve_auth


def test_parse_cli_headers_accepts_repeated_name_value_pairs() -> None:
    headers = parse_cli_headers(
        [
            "Authorization: Bearer flag-token",
            "X-Request-Source: agora-oauth",
        ]
    )

    assert headers == {
        "Authorization": "Bearer flag-token",
        "X-Request-Source": "agora-oauth",
    }


def test_collect_env_headers_reads_single_header_value() -> None:
    headers = collect_env_headers(
        {
            "ATLASSIAN_HEADER": "Authorization: Bearer env-token",
            "UNRELATED_ENV": "ignored",
        }
    )

    assert headers == {
        "Authorization": "Bearer env-token",
    }


def test_resolve_auth_preserves_injected_headers() -> None:
    auth = resolve_auth(
        auth=AuthMode.BASIC,
        username="alice",
        password=None,
        token="legacy-token",
        headers={"Authorization": "Bearer oauth-token"},
    )

    assert auth.mode is AuthMode.BASIC
    assert auth.headers == {"Authorization": "Bearer oauth-token"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/auth/test_headers.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.auth.headers` or missing `headers` on `ResolvedAuth`

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field


class ResolvedAuth(BaseModel):
    mode: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
```

```python
from atlassian_cli.auth.models import AuthMode, ResolvedAuth


def resolve_auth(
    *,
    auth: AuthMode | None,
    username: str | None,
    password: str | None,
    token: str | None,
    headers: dict[str, str] | None = None,
) -> ResolvedAuth:
    mode = auth or AuthMode.BASIC
    return ResolvedAuth(
        mode=mode,
        username=username,
        password=password,
        token=token,
        headers=headers or {},
    )
```

```python
def _canonical_header_name(suffix: str) -> str:
    special_cases = {
        "AUTHORIZATION": "Authorization",
        "COOKIE": "Cookie",
    }
    if suffix in special_cases:
        return special_cases[suffix]
    return "-".join(part.capitalize() for part in suffix.split("_"))


def parse_cli_headers(values: list[str] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values or []:
        if ":" not in value:
            raise ValueError(f"Invalid header format: {value}")
        name, raw = value.split(":", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid header format: {value}")
        headers[name] = raw.lstrip()
    return headers


def collect_env_headers(env: dict[str, str]) -> dict[str, str]:
    value = env.get("ATLASSIAN_HEADER")
    if not value:
        return {}
    return parse_cli_headers([value])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/auth/test_headers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/auth/models.py src/atlassian_cli/auth/resolver.py src/atlassian_cli/auth/headers.py tests/auth/test_headers.py
git commit -m "feat: add header parsing primitives"
```

### Task 2: Merge CLI flags and environment headers into runtime context

**Files:**
- Modify: `src/atlassian_cli/config/models.py`
- Modify: `src/atlassian_cli/config/resolver.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/config/test_resolver.py`
- Modify: `tests/test_cli_context.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context


def test_flag_headers_override_environment_headers() -> None:
    profile = ProfileConfig(
        name="prod-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        auth=AuthMode.PAT,
        token="legacy-token",
    )
    env = {
        "ATLASSIAN_HEADER": "X-Request-Source: agora-oauth",
    }
    overrides = RuntimeOverrides(
        url="https://bitbucket.example.com",
        headers={"accessToken": "flag-token"},
    )

    context = resolve_runtime_context(profile=profile, env=env, overrides=overrides)

    assert context.auth.headers == {
        "accessToken": "flag-token",
        "X-Request-Source": "agora-oauth",
    }
```

```python
from pathlib import Path

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_callback_reads_header_flag_and_env(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '''
        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"
        '''.strip()
    )

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
                        "Authorization": context.auth.headers.get("Authorization"),
                        "X-Request-Source": context.auth.headers.get("X-Request-Source"),
                    }
                ]
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "--profile",
            "prod_bitbucket",
            "--header",
            "accessToken: flag-token",
            "bitbucket",
            "project",
            "list",
            "--output",
            "json",
        ],
        env={"ATLASSIAN_HEADER": "X-Request-Source: agora-oauth"},
    )

    assert result.exit_code == 0
    assert '"accessToken": "flag-token"' in result.stdout
    assert '"X-Request-Source": "agora-oauth"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/test_cli_context.py -v`
Expected: FAIL because `RuntimeOverrides` does not accept `headers` and CLI does not expose `--header`

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field


class RuntimeOverrides(BaseModel):
    profile: str | None = None
    product: Product | None = None
    deployment: Deployment | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    token: str | None = None
    auth: AuthMode | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    output: str = Field(default="table")
```

```python
from atlassian_cli.auth.headers import collect_env_headers
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
    env_headers = collect_env_headers(env)
    headers = {**env_headers, **overrides.headers}
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

```python
from atlassian_cli.auth.headers import parse_cli_headers


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
    ...
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
            headers=parse_cli_headers(header),
            output=output,
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/test_cli_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/models.py src/atlassian_cli/config/resolver.py src/atlassian_cli/cli.py tests/config/test_resolver.py tests/test_cli_context.py
git commit -m "feat: wire header injection into runtime context"
```

### Task 3: Prefer injected headers when constructing product providers

**Files:**
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Create: `tests/products/test_header_providers.py`

- [ ] **Step 1: Write the failing test**

```python
from atlassian_cli.auth.models import AuthMode, ResolvedAuth
from atlassian_cli.config.models import Deployment, Product
from atlassian_cli.core.context import ExecutionContext
from atlassian_cli.products.factory import build_provider


def test_bitbucket_provider_prefers_injected_headers(monkeypatch) -> None:
    captured = {}

    class FakeBitbucket:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("atlassian_cli.products.bitbucket.providers.server.Bitbucket", FakeBitbucket)

    context = ExecutionContext(
        profile="oauth-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        output="json",
        auth=ResolvedAuth(
            mode=AuthMode.PAT,
            token="legacy-token",
            headers={"Authorization": "Bearer oauth-token"},
        ),
    )

    build_provider(context)

    assert captured["url"] == "https://bitbucket.example.com"
    assert captured["header"] == {"Authorization": "Bearer oauth-token"}
    assert "password" not in captured or captured["password"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/products/test_header_providers.py -v`
Expected: FAIL because providers do not accept or forward `header`

- [ ] **Step 3: Write minimal implementation**

```python
class JiraServerProvider:
    def __init__(
        self,
        *,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if headers:
            kwargs["header"] = headers
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Jira(**kwargs)
```

```python
class ConfluenceServerProvider:
    def __init__(
        self,
        *,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if headers:
            kwargs["header"] = headers
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Confluence(**kwargs)
```

```python
class BitbucketServerProvider:
    def __init__(
        self,
        *,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if headers:
            kwargs["header"] = headers
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Bitbucket(**kwargs)
```

```python
def build_provider(context):
    ...
    if context.product is Product.BITBUCKET:
        return BitbucketServerProvider(
            url=context.url,
            username=context.auth.username,
            password=context.auth.password,
            token=context.auth.token,
            headers=context.auth.headers,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/products/test_header_providers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/providers/server.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/bitbucket/providers/server.py tests/products/test_header_providers.py
git commit -m "feat: pass injected headers to providers"
```

### Task 4: Document header usage and verify Bitbucket real flow with injected headers

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing verification**

```bash
rg -n "ATLASSIAN_HEADER|--header" README.md
```

- [ ] **Step 2: Run command to verify current docs and flow are insufficient**

Run: `rg -n "ATLASSIAN_HEADER|--header" README.md`
Expected: no matches for the new header-based usage

- [ ] **Step 3: Write minimal implementation**

```markdown
## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.agoralab.co --header 'Authorization: Bearer ...' bitbucket pr list SDK rte_sdk --output json`

Environment variable example:

- `export ATLASSIAN_HEADER='Authorization: Bearer ...'`
- `atlassian --url https://bitbucket.agoralab.co bitbucket pr list SDK rte_sdk --output json`
```

- [ ] **Step 4: Run verification commands**

Run: `rg -n "ATLASSIAN_HEADER|--header" README.md`
Expected: matches for both flag-based and env-based header usage

Run: `ATLASSIAN_HEADER='Authorization: Bearer test-token' .venv/bin/atlassian --url https://bitbucket.example.com bitbucket project list --output json`
Expected: request path executes using injected header. In environments without a valid token, failure should reflect remote auth outcome rather than local CLI argument validation.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add header injection usage examples"
```

## Self-Review Notes

- Spec coverage:
  - `--header` support is covered by Tasks 1 and 2.
  - `ATLASSIAN_HEADER` environment parsing is covered by Tasks 1 and 2.
  - provider precedence for injected headers is covered by Task 3.
  - user-facing documentation and real-flow verification are covered by Task 4.
- Gaps checked:
  - no profile persistence is added for injected headers, matching the spec
  - no Agora-specific code is added to the CLI, matching the non-invasive boundary
  - existing `basic/bearer/pat` flows remain available when no injected headers are present
