# Atlassian CLI Config Headers Command Substitution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add top-level and profile-scoped config-backed HTTP headers, including `$(...)` command substitution in header values, so users can source values from tools such as `example-oauth` directly from `config.toml`.

**Architecture:** Extend config loading to understand `[headers]` and `[profiles.<name>.headers]`, then resolve those header maps at runtime with command substitution before merging them with repeated `--header` flags. Keep header parsing for CLI flags in `auth/headers.py` and move config-header command evaluation into a focused config helper.

**Tech Stack:** Python 3.13, Typer, Pydantic, atlassian-python-api, pytest, subprocess

---

## Planned File Structure

### Create

- `src/atlassian_cli/config/header_substitution.py`
- `tests/config/test_header_substitution.py`

### Modify

- `src/atlassian_cli/config/models.py`
- `src/atlassian_cli/config/loader.py`
- `src/atlassian_cli/config/resolver.py`
- `src/atlassian_cli/auth/headers.py`
- `src/atlassian_cli/cli.py`
- `tests/config/test_loader.py`
- `tests/config/test_resolver.py`
- `tests/auth/test_headers.py`
- `tests/test_cli_context.py`
- `README.md`

### Responsibility Notes

- `config/models.py` owns typed config representation for top-level and profile-scoped header maps.
- `config/loader.py` owns TOML parsing and translation of invalid config values into `ConfigError`.
- `config/header_substitution.py` owns `$(...)` parsing, `/bin/sh -lc` execution, and output validation for config-backed header values.
- `config/resolver.py` owns precedence merging across top-level config headers, profile config headers, and repeated `--header` flags.
- `auth/headers.py` remains the parser for repeated `--header 'Name: value'` CLI flags only.
- `cli.py` only loads config, selects the base profile, and hands raw data to the resolver.

### Common Commands

- Focused loader tests: `.venv/bin/python -m pytest tests/config/test_loader.py -v`
- Focused substitution tests: `.venv/bin/python -m pytest tests/config/test_header_substitution.py -v`
- Focused resolver tests: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/auth/test_headers.py -v`
- Focused CLI tests: `.venv/bin/python -m pytest tests/test_cli_context.py -v`
- Combined verification: `.venv/bin/python -m pytest tests/auth/test_headers.py tests/config/test_loader.py tests/config/test_header_substitution.py tests/config/test_resolver.py tests/test_cli_context.py -v`

## Task 1: Load Top-Level and Profile Config Headers

**Files:**
- Modify: `src/atlassian_cli/config/models.py`
- Modify: `src/atlassian_cli/config/loader.py`
- Modify: `tests/config/test_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from atlassian_cli.config.loader import load_config, load_profiles
from atlassian_cli.core.errors import ConfigError, UnsupportedError


def test_load_config_reads_top_level_and_profile_headers(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"

        [profiles.prod_bitbucket.headers]
        accessToken = "$(example-oauth token --profile prod_bitbucket)"
        """.strip()
    )

    config = load_config(config_file)

    assert config.headers == {
        "X-Request-Source": "config-default",
    }
    assert config.profiles["prod_bitbucket"].headers == {
        "accessToken": "$(example-oauth token --profile prod_bitbucket)",
    }


def test_load_config_rejects_non_string_header_values(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        accessToken = 42
        """.strip()
    )

    with pytest.raises(ConfigError, match="headers"):
        load_config(config_file)


def test_load_profiles_preserves_existing_profile_lookup(tmp_path: Path) -> None:
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

        [profiles.prod_jira.headers]
        X-Request-Source = "profile-default"
        """.strip()
    )

    profiles = load_profiles(config_file)

    assert profiles["prod_jira"].headers == {
        "X-Request-Source": "profile-default",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_loader.py -v`
Expected: FAIL with `ImportError` for `load_config`, missing `headers` on config models, or loader not raising `ConfigError` for non-string header values

- [ ] **Step 3: Write the minimal implementation**

```python
from enum import StrEnum

from pydantic import BaseModel, Field, StrictStr

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
    headers: dict[str, StrictStr] = Field(default_factory=dict)


class LoadedConfig(BaseModel):
    headers: dict[str, StrictStr] = Field(default_factory=dict)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
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
            profiles=profiles,
        )
    except ValidationError as exc:
        raise ConfigError(f"Invalid config.toml headers configuration: {exc}") from exc


def load_profiles(path: Path) -> dict[str, ProfileConfig]:
    return load_config(path).profiles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/models.py src/atlassian_cli/config/loader.py tests/config/test_loader.py
git commit -m "feat: load config-backed header maps"
```

## Task 2: Add Config Header Command Substitution

**Files:**
- Create: `src/atlassian_cli/config/header_substitution.py`
- Create: `tests/config/test_header_substitution.py`

- [ ] **Step 1: Write the failing tests**

```python
import subprocess

import pytest

from atlassian_cli.config.header_substitution import run_header_command, substitute_header_commands
from atlassian_cli.core.errors import ConfigError


def test_substitute_header_commands_replaces_command_output() -> None:
    resolved = substitute_header_commands(
        value="Bearer $(example-oauth token)",
        source="[headers]",
        header_name="Authorization",
        runner=lambda command: "oauth-token" if command == "example-oauth token" else "",
    )

    assert resolved == "Bearer oauth-token"


def test_substitute_header_commands_supports_multiple_substitutions() -> None:
    outputs = {
        "whoami": "alice",
        "example-oauth token": "oauth-token",
    }
    resolved = substitute_header_commands(
        value="User $(whoami) Token $(example-oauth token)",
        source="[profiles.code.headers]",
        header_name="X-Debug",
        runner=lambda command: outputs[command],
    )

    assert resolved == "User alice Token oauth-token"


def test_substitute_header_commands_rejects_malformed_syntax() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        substitute_header_commands(
            value="$(example-oauth token",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "ignored",
        )


def test_substitute_header_commands_rejects_empty_command_body() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        substitute_header_commands(
            value="prefix $() suffix",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "ignored",
        )


def test_substitute_header_commands_rejects_nested_commands() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        substitute_header_commands(
            value="$(echo $(whoami))",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "ignored",
        )


def test_substitute_header_commands_rejects_empty_output() -> None:
    with pytest.raises(ConfigError, match="empty output"):
        substitute_header_commands(
            value="$(example-oauth token)",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "   ",
        )


def test_substitute_header_commands_rejects_multiline_output() -> None:
    with pytest.raises(ConfigError, match="single line"):
        substitute_header_commands(
            value="$(example-oauth token)",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "line-one\\nline-two",
        )


def test_run_header_command_raises_for_non_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=7,
            stdout="",
            stderr="oauth failed",
        ),
    )

    with pytest.raises(ConfigError, match="exit code 7"):
        run_header_command("example-oauth token")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_header_substitution.py -v`
Expected: FAIL with `ModuleNotFoundError` for `atlassian_cli.config.header_substitution`

- [ ] **Step 3: Write the minimal implementation**

```python
import subprocess
from collections.abc import Callable

from atlassian_cli.core.errors import ConfigError

CommandRunner = Callable[[str], str]


def run_header_command(command: str) -> str:
    completed = subprocess.run(
        ["/bin/sh", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ConfigError(
            f"Header command failed with exit code {completed.returncode}: {command}"
        )
    return completed.stdout


def substitute_header_commands(
    *,
    value: str,
    source: str,
    header_name: str,
    runner: CommandRunner | None = None,
) -> str:
    resolved = value
    runner = runner or run_header_command
    while "$(" in resolved:
        start = resolved.find("$(")
        end = resolved.find(")", start + 2)
        if start == -1 or end == -1:
            raise ConfigError(f"Malformed command substitution in {source}.{header_name}")
        command = resolved[start + 2 : end].strip()
        if not command or "$(" in command:
            raise ConfigError(f"Malformed command substitution in {source}.{header_name}")
        output = runner(command).strip()
        if not output:
            raise ConfigError(f"Header command produced empty output for {source}.{header_name}")
        if "\n" in output:
            raise ConfigError(f"Header command must produce a single line for {source}.{header_name}")
        resolved = f"{resolved[:start]}{output}{resolved[end + 1:]}"
    return resolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_header_substitution.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/header_substitution.py tests/config/test_header_substitution.py
git commit -m "feat: add config header command substitution"
```

## Task 3: Merge Config Headers in the Runtime Resolver

**Files:**
- Modify: `src/atlassian_cli/config/resolver.py`
- Modify: `src/atlassian_cli/auth/headers.py`
- Modify: `tests/config/test_resolver.py`
- Modify: `tests/auth/test_headers.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.auth.models import AuthMode
from atlassian_cli.config.models import Deployment, Product, ProfileConfig, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context


def test_profile_headers_override_top_level_headers() -> None:
    profile = ProfileConfig(
        name="prod-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        auth=AuthMode.PAT,
        token="legacy-token",
        headers={
            "accessToken": "$(example-oauth token --profile prod-bitbucket)",
            "X-Request-Source": "profile-default",
        },
    )

    context = resolve_runtime_context(
        profile=profile,
        env={},
        default_headers={
            "X-Request-Source": "top-level-default",
            "X-Trace": "top-level-trace",
        },
        overrides=RuntimeOverrides(url="https://bitbucket.example.com"),
        command_runner=lambda command: "profile-token",
    )

    assert context.auth.headers == {
        "accessToken": "profile-token",
        "X-Request-Source": "profile-default",
        "X-Trace": "top-level-trace",
    }


def test_flag_headers_override_config_headers() -> None:
    profile = ProfileConfig(
        name="prod-bitbucket",
        product=Product.BITBUCKET,
        deployment=Deployment.SERVER,
        url="https://bitbucket.example.com",
        auth=AuthMode.PAT,
        token="legacy-token",
        headers={"accessToken": "$(example-oauth token)"},
    )

    context = resolve_runtime_context(
        profile=profile,
        env={},
        default_headers={"X-Trace": "top-level-trace"},
        overrides=RuntimeOverrides(
            url="https://bitbucket.example.com",
            headers={"accessToken": "flag-token"},
        ),
        command_runner=lambda command: "profile-token",
    )

    assert context.auth.headers == {
        "accessToken": "flag-token",
        "X-Trace": "top-level-trace",
    }
```

```python
import pytest

from atlassian_cli.auth.headers import parse_cli_headers


def test_parse_cli_headers_rejects_missing_colon() -> None:
    with pytest.raises(ValueError, match="Invalid header format"):
        parse_cli_headers(["Authorization"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/auth/test_headers.py -v`
Expected: FAIL because `resolve_runtime_context` does not accept `default_headers` or `command_runner`

- [ ] **Step 3: Write the minimal implementation**

```python
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
```

```python
import atlassian_cli.config.header_substitution as header_substitution

from atlassian_cli.auth.resolver import resolve_auth
from atlassian_cli.core.context import ExecutionContext


def resolve_runtime_context(
    *,
    profile,
    env: dict[str, str],
    default_headers: dict[str, str] | None,
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
    config_headers = header_substitution.resolve_header_map(
        default_headers or {},
        source="[headers]",
        runner=command_runner,
    )
    profile_headers = header_substitution.resolve_header_map(
        profile.headers,
        source=f"[profiles.{profile.name}.headers]",
        runner=command_runner,
    )
    headers = {**config_headers, **profile_headers, **overrides.headers}
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
def resolve_header_map(
    headers: dict[str, str],
    *,
    source: str,
    runner=None,
) -> dict[str, str]:
    return {
        name: substitute_header_commands(
            value=value,
            source=source,
            header_name=name,
            runner=runner,
        )
        for name, value in headers.items()
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/config/test_resolver.py tests/auth/test_headers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/config/resolver.py src/atlassian_cli/auth/headers.py tests/config/test_resolver.py tests/auth/test_headers.py src/atlassian_cli/config/header_substitution.py
git commit -m "feat: merge config-backed headers into runtime context"
```

## Task 4: Wire Config Headers Through the CLI Entry Point

**Files:**
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/test_cli_context.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import atlassian_cli.config.header_substitution as header_substitution
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_callback_reads_top_level_and_profile_headers_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [headers]
        X-Request-Source = "config-default"

        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"

        [profiles.prod_bitbucket.headers]
        accessToken = "$(example-oauth token)"
        """.strip()
    )

    monkeypatch.setattr(
        header_substitution,
        "run_header_command",
        lambda command: "profile-token",
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
                        "accessToken": context.auth.headers.get("accessToken"),
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
            "bitbucket",
            "project",
            "list",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"accessToken": "profile-token"' in result.stdout
    assert '"X-Request-Source": "config-default"' in result.stdout


def test_root_callback_flag_headers_override_config_headers(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [profiles.prod_bitbucket]
        product = "bitbucket"
        deployment = "server"
        url = "https://bitbucket.example.com"
        auth = "pat"
        token = "legacy-token"

        [profiles.prod_bitbucket.headers]
        accessToken = "$(example-oauth token)"
        """.strip()
    )

    monkeypatch.setattr(
        header_substitution,
        "run_header_command",
        lambda command: "profile-token",
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
                    {"accessToken": context.auth.headers.get("accessToken")}
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
    )

    assert result.exit_code == 0
    assert '"accessToken": "flag-token"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli_context.py -v`
Expected: FAIL because `cli.py` still loads only profiles and never passes top-level config headers to the runtime resolver

- [ ] **Step 3: Write the minimal implementation**

```python
from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Deployment, LoadedConfig, Product, ProfileConfig, RuntimeOverrides


@app.callback()
def root_callback(...):
    if ctx.invoked_subcommand is None:
        return

    config = load_config(config_file) if config_file.exists() else LoadedConfig()
    profiles = config.profiles
    if profile:
        selected_profile = profiles.get(profile)
        if selected_profile is None:
            raise typer.BadParameter(f"Unknown profile: {profile}", param_hint="--profile")
    elif url is None:
        selected_profile = next(iter(profiles.values()), None)
    else:
        selected_profile = None

    ...

    base_profile = selected_profile or ProfileConfig(
        name=profile or f"inline-{product.value}",
        product=product,
        deployment=deployment or Deployment.SERVER,
        url=url or "",
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

Run: `.venv/bin/python -m pytest tests/test_cli_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py tests/test_cli_context.py
git commit -m "feat: wire config-backed headers into cli context"
```

## Task 5: Update User-Facing Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing doc check**

Run: `rg -n "\[headers\]|profiles\\..*headers|example-oauth token|ATLASSIAN_HEADER" README.md`
Expected: output shows `ATLASSIAN_HEADER` examples and no config-backed `[headers]` examples

- [ ] **Step 2: Write the documentation update**

````md
## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.example.com --header 'accessToken: ...' bitbucket pr list SDK rte_sdk --output json`

Config file example:

```toml
[headers]
accessToken = "$(example-oauth token)"

[profiles.code]
product = "bitbucket"
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"

[profiles.code.headers]
X-Request-Source = "example-oauth"
```

- `atlassian --profile code bitbucket pr list SDK rte_sdk --output json`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.
````

- [ ] **Step 3: Run the doc check again**

Run: `rg -n "\[headers\]|profiles\\..*headers|example-oauth token|ATLASSIAN_HEADER" README.md`
Expected: matches for `[headers]`, profile header examples, and `example-oauth token`, with no `ATLASSIAN_HEADER` matches

- [ ] **Step 4: Run the combined verification**

Run: `.venv/bin/python -m pytest tests/auth/test_headers.py tests/config/test_loader.py tests/config/test_header_substitution.py tests/config/test_resolver.py tests/test_cli_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/auth/test_headers.py tests/config/test_loader.py tests/config/test_header_substitution.py tests/config/test_resolver.py tests/test_cli_context.py src/atlassian_cli/config/models.py src/atlassian_cli/config/loader.py src/atlassian_cli/config/header_substitution.py src/atlassian_cli/config/resolver.py src/atlassian_cli/auth/headers.py src/atlassian_cli/cli.py
git commit -m "docs: document config-backed header substitution"
```
