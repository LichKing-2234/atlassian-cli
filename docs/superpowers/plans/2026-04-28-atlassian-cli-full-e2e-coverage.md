# Atlassian CLI Full E2E Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only live e2e suite that covers every CLI subcommand with at least one real command chain, including real write operations against the configured Jira, Confluence, and Bitbucket instances.

**Architecture:** Start by fixing the two command paths that are currently not trustworthy for live coverage: `confluence attachment download` does not download anything, and `bitbucket repo create` does not match the installed SDK contract. Then add a small shared `tests/e2e/support` layer for environment loading, real CLI execution, cleanup tracking, unique naming, runtime context creation, and temporary git sandboxes. Build product-split live suites on top of that support layer, and lock the CLI surface with a manifest test that compares the declared live coverage map against the discovered Typer command tree.

**Tech Stack:** Python 3.13, pytest, Typer, atlassian-python-api, subprocess, git, Pydantic v2

---

## Planned File Structure

### Create

- `tests/products/confluence/test_attachment_command.py`
- `tests/products/confluence/test_attachment_service.py`
- `tests/e2e/conftest.py`
- `tests/e2e/coverage_manifest.py`
- `tests/e2e/support/__init__.py`
- `tests/e2e/support/cleanup.py`
- `tests/e2e/support/context.py`
- `tests/e2e/support/env.py`
- `tests/e2e/support/git.py`
- `tests/e2e/support/names.py`
- `tests/e2e/support/runner.py`
- `tests/e2e/test_support.py`
- `tests/e2e/test_coverage_manifest.py`
- `tests/e2e/test_jira_live.py`
- `tests/e2e/test_confluence_live.py`
- `tests/e2e/test_bitbucket_live.py`

### Modify

- `src/atlassian_cli/products/confluence/providers/server.py`
- `src/atlassian_cli/products/bitbucket/providers/server.py`
- `tests/products/confluence/test_provider.py`
- `tests/products/bitbucket/test_provider.py`
- `tests/products/bitbucket/test_repo_service.py`
- `tests/products/bitbucket/test_repo_command.py`
- `README.md`
- `tests/test_readme.py`

### Delete

- `tests/e2e/test_live_cli.py`

### Responsibility Notes

- `src/atlassian_cli/products/confluence/providers/server.py` owns the real remote download path for Confluence attachments.
- `src/atlassian_cli/products/bitbucket/providers/server.py` owns the SDK-facing Bitbucket repo-creation contract.
- `tests/e2e/support/env.py` owns all live environment parsing and defaults.
- `tests/e2e/support/runner.py` owns real CLI subprocess execution and JSON/error helpers.
- `tests/e2e/support/cleanup.py` owns best-effort reverse-order cleanup with residue reporting.
- `tests/e2e/support/context.py` owns building real `ExecutionContext` objects and server providers from the user's existing config so tests can do out-of-band cleanup where the CLI has no delete command.
- `tests/e2e/support/git.py` owns temporary clone, branch, commit, push, and remote branch deletion for Bitbucket PR setup.
- `tests/e2e/coverage_manifest.py` owns the declared mapping from CLI subcommands to live tests.
- Product live test files own only product-specific scenario chains and assertions.

### Common Commands

- Confluence provider/attachment tests: `.venv/bin/python -m pytest tests/products/confluence/test_provider.py tests/products/confluence/test_attachment_service.py tests/products/confluence/test_attachment_command.py -v`
- Bitbucket provider/repo tests: `.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py -v`
- E2E support and manifest tests: `.venv/bin/python -m pytest tests/e2e/test_support.py tests/e2e/test_coverage_manifest.py -v`
- Live Jira suite: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_jira_live.py -m e2e -v`
- Live Confluence suite: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_confluence_live.py -m e2e -v`
- Live Bitbucket suite: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_bitbucket_live.py -m e2e -v`
- Docs contract tests: `.venv/bin/python -m pytest tests/test_readme.py tests/test_cli_help.py tests/integration/test_smoke.py -v`

## Task 1: Align Bitbucket Repo Creation With The Installed SDK

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Modify: `tests/products/bitbucket/test_provider.py`
- Modify: `tests/products/bitbucket/test_repo_service.py`
- Modify: `tests/products/bitbucket/test_repo_command.py`
- Test: `tests/products/bitbucket/test_provider.py`
- Test: `tests/products/bitbucket/test_repo_service.py`
- Test: `tests/products/bitbucket/test_repo_command.py`

- [ ] **Step 1: Write the failing tests**

Append this provider test to `tests/products/bitbucket/test_provider.py`:

```python
def test_create_repo_forwards_project_key_and_name_to_sdk() -> None:
    calls = {}

    class FakeClient:
        def create_repo(
            self,
            project_key: str,
            repository_slug: str,
            forkable: bool = False,
            is_private: bool = True,
        ):
            calls["args"] = (project_key, repository_slug, forkable, is_private)
            return {
                "slug": "atlassian-cli-e2e-temp",
                "name": repository_slug,
                "project": {"key": project_key},
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.create_repo(
        project_key="~example_user",
        name="atlassian-cli-e2e-temp",
        scm_id="git",
    )

    assert result["slug"] == "atlassian-cli-e2e-temp"
    assert calls["args"] == (
        "~example_user",
        "atlassian-cli-e2e-temp",
        False,
        True,
    )
```

Append this service test to `tests/products/bitbucket/test_repo_service.py`:

```python
def test_repo_service_create_normalizes_repo_payload() -> None:
    class CreateRepoProvider(FakeRepoProvider):
        def create_repo(self, project_key: str, name: str, scm_id: str) -> dict:
            assert project_key == "~example_user"
            assert name == "atlassian-cli-e2e-temp"
            assert scm_id == "git"
            return {
                "slug": "atlassian-cli-e2e-temp",
                "name": "atlassian-cli-e2e-temp",
                "state": "AVAILABLE",
                "project": {"key": "~example_user", "name": "example_user"},
            }

    service = RepoService(provider=CreateRepoProvider())

    result = service.create("~example_user", "atlassian-cli-e2e-temp", "git")

    assert result == {
        "slug": "atlassian-cli-e2e-temp",
        "name": "atlassian-cli-e2e-temp",
        "state": "AVAILABLE",
        "project": {"key": "~example_user", "name": "example_user"},
    }
```

Append this command test to `tests/products/bitbucket/test_repo_command.py`:

```python
def test_bitbucket_repo_create_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import repo as repo_module

    monkeypatch.setattr(
        repo_module,
        "build_repo_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "create": lambda self, project_key, name, scm_id: {
                    "slug": "atlassian-cli-e2e-temp",
                    "name": name,
                    "project": {"key": project_key},
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "repo",
            "create",
            "--project",
            "~example_user",
            "--name",
            "atlassian-cli-e2e-temp",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"slug": "atlassian-cli-e2e-temp"' in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py -v`

Expected: FAIL because `BitbucketServerProvider.create_repo()` currently calls the SDK with unsupported keyword arguments, and the new create-path tests do not pass yet.

- [ ] **Step 3: Write the minimal implementation**

Replace `create_repo()` in `src/atlassian_cli/products/bitbucket/providers/server.py` with:

```python
    def create_repo(self, *, project_key: str, name: str, scm_id: str) -> dict:
        del scm_id
        return self.client.create_repo(project_key, name)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/bitbucket/providers/server.py tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py
git commit -m "fix: align bitbucket repo creation with sdk"
```

## Task 2: Implement Real Confluence Attachment Downloads

**Files:**
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `tests/products/confluence/test_provider.py`
- Create: `tests/products/confluence/test_attachment_service.py`
- Create: `tests/products/confluence/test_attachment_command.py`
- Test: `tests/products/confluence/test_provider.py`
- Test: `tests/products/confluence/test_attachment_service.py`
- Test: `tests/products/confluence/test_attachment_command.py`

- [ ] **Step 1: Write the failing tests**

Append this provider test to `tests/products/confluence/test_provider.py`:

```python
def test_download_attachment_writes_file_to_destination(tmp_path) -> None:
    calls: list[tuple[str, object]] = []

    class FakeClient:
        def get(self, path: str, params=None, not_json_response: bool = False):
            calls.append((path, params if params is not None else not_json_response))
            if path == "rest/api/content/55":
                return {
                    "id": "55",
                    "title": "deploy.log",
                    "_links": {"download": "/download/attachments/55/deploy.log"},
                }
            assert path == "/download/attachments/55/deploy.log"
            assert not_json_response is True
            return b"release=42\nstatus=ok\n"

    provider = build_provider_with_client(FakeClient())

    result = provider.download_attachment("55", str(tmp_path))

    output_path = tmp_path / "deploy.log"
    assert output_path.read_bytes() == b"release=42\nstatus=ok\n"
    assert result == {
        "attachment_id": "55",
        "title": "deploy.log",
        "path": str(output_path),
        "bytes_written": 21,
    }
    assert calls[0] == ("rest/api/content/55", {"expand": "version"})
```

Create `tests/products/confluence/test_attachment_service.py` with:

```python
from atlassian_cli.products.confluence.services.attachment import AttachmentService


class FakeAttachmentProvider:
    def list_attachments(self, page_id: str) -> dict:
        return {
            "results": [
                {
                    "id": "55",
                    "title": "deploy.log",
                    "_links": {"download": "/download/attachments/55/deploy.log"},
                }
            ]
        }

    def upload_attachment(self, page_id: str, file_path: str) -> dict:
        return {"id": "55", "title": "deploy.log"}

    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        return {
            "attachment_id": attachment_id,
            "title": "deploy.log",
            "path": destination,
            "bytes_written": 21,
        }


def test_attachment_service_download_returns_provider_payload() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.download("55", "/tmp/deploy.log")

    assert result == {
        "attachment_id": "55",
        "title": "deploy.log",
        "path": "/tmp/deploy.log",
        "bytes_written": 21,
    }
```

Create `tests/products/confluence/test_attachment_command.py` with:

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_confluence_attachment_download_outputs_json(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.confluence.commands import attachment as attachment_module

    target = tmp_path / "deploy.log"
    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "download": lambda self, attachment_id, destination: {
                    "attachment_id": attachment_id,
                    "path": destination,
                    "bytes_written": 21,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "attachment",
            "download",
            "55",
            "--destination",
            str(target),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"attachment_id": "55"' in result.stdout
    assert str(target) in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/products/confluence/test_provider.py tests/products/confluence/test_attachment_service.py tests/products/confluence/test_attachment_command.py -v`

Expected: FAIL because `ConfluenceServerProvider.download_attachment()` currently returns a synthetic payload without fetching metadata or writing a file.

- [ ] **Step 3: Write the minimal implementation**

Replace `download_attachment()` in `src/atlassian_cli/products/confluence/providers/server.py` with:

```python
    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        from pathlib import Path

        attachment = self.client.get(
            f"rest/api/content/{attachment_id}",
            params={"expand": "version"},
        )
        title = str(attachment.get("title") or attachment_id)
        links = attachment.get("_links") if isinstance(attachment.get("_links"), dict) else {}
        download_link = links.get("download")
        if not isinstance(download_link, str) or not download_link:
            raise RuntimeError(f"attachment download url missing for {attachment_id}")

        target = Path(destination)
        if target.exists() and target.is_dir():
            target = target / title
        elif destination.endswith("/") or destination.endswith("\\"):
            target.mkdir(parents=True, exist_ok=True)
            target = target / title
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        payload = self.client.get(download_link, not_json_response=True)
        content = bytes(payload)
        target.write_bytes(content)
        return {
            "attachment_id": str(attachment_id),
            "title": title,
            "path": str(target),
            "bytes_written": len(content),
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/products/confluence/test_provider.py tests/products/confluence/test_attachment_service.py tests/products/confluence/test_attachment_command.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/confluence/providers/server.py tests/products/confluence/test_provider.py tests/products/confluence/test_attachment_service.py tests/products/confluence/test_attachment_command.py
git commit -m "fix: implement confluence attachment download"
```

## Task 3: Add The Shared Live E2E Support Layer

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/support/__init__.py`
- Create: `tests/e2e/support/cleanup.py`
- Create: `tests/e2e/support/context.py`
- Create: `tests/e2e/support/env.py`
- Create: `tests/e2e/support/git.py`
- Create: `tests/e2e/support/names.py`
- Create: `tests/e2e/support/runner.py`
- Create: `tests/e2e/test_support.py`
- Test: `tests/e2e/test_support.py`

- [ ] **Step 1: Write the failing helper tests**

Create `tests/e2e/test_support.py` with:

```python
import subprocess
import sys
from pathlib import Path

import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support.cleanup import CleanupRegistry
from tests.e2e.support.context import build_live_context
from tests.e2e.support.env import LiveEnv, load_live_env
from tests.e2e.support.names import unique_name
from tests.e2e.support.runner import run_cli


def test_load_live_env_uses_defaults(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))
    monkeypatch.delenv("ATLASSIAN_E2E_JIRA_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", raising=False)
    monkeypatch.delenv("ATLASSIAN_E2E_BITBUCKET_REPO", raising=False)

    env = load_live_env()

    assert env == LiveEnv(
        config_file=config_file,
        jira_project="TEST",
        confluence_space="~user@example.com",
        bitbucket_project="~example_user",
        bitbucket_create_project="EXAMPLE",
        bitbucket_repo="example-e2e-repo",
    )


def test_cleanup_registry_runs_in_reverse_order() -> None:
    calls: list[str] = []
    registry = CleanupRegistry()

    registry.add("first", lambda: calls.append("first"))
    registry.add("second", lambda: calls.append("second"))
    registry.run()

    assert calls == ["second", "first"]


def test_unique_name_includes_prefix() -> None:
    value = unique_name("issue")
    assert value.startswith("issue-")
    assert len(value) > len("issue-")


def test_run_cli_includes_config_file(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    live_env = LiveEnv(
        config_file=tmp_path / "config.toml",
        jira_project="TEST",
        confluence_space="~user@example.com",
        bitbucket_project="~example_user",
        bitbucket_create_project="EXAMPLE",
        bitbucket_repo="example-e2e-repo",
    )

    run_cli(live_env, "jira", "project", "list", "--output", "json")

    assert calls["command"][:5] == [
        sys.executable,
        "-m",
        "atlassian_cli.main",
        "--config-file",
        str(live_env.config_file),
    ]
    assert "PYTHONPATH" in calls["env"]


def test_build_live_context_reads_product_config(tmp_path, monkeypatch) -> None:
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
    monkeypatch.setenv("ATLASSIAN_E2E", "1")
    monkeypatch.setenv("ATLASSIAN_CONFIG_FILE", str(config_file))

    env = load_live_env()
    context = build_live_context(Product.JIRA, env)

    assert context.product is Product.JIRA
    assert context.url == "https://jira.example.com"
    assert context.auth.username == "alice"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/e2e/test_support.py -v`

Expected: FAIL because the `tests.e2e.support` modules do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create `tests/e2e/support/env.py` with:

```python
import os
from dataclasses import dataclass
from pathlib import Path

from atlassian_cli.cli import DEFAULT_CONFIG_FILE


@dataclass(frozen=True)
class LiveEnv:
    config_file: Path
    jira_project: str
    confluence_space: str
    bitbucket_project: str
    bitbucket_repo: str


def load_live_env() -> LiveEnv:
    if os.getenv("ATLASSIAN_E2E") != "1":
        raise RuntimeError("ATLASSIAN_E2E=1 is required for live e2e tests")
    config_file = Path(os.getenv("ATLASSIAN_CONFIG_FILE", str(DEFAULT_CONFIG_FILE))).expanduser()
    return LiveEnv(
        config_file=config_file,
        jira_project=os.getenv("ATLASSIAN_E2E_JIRA_PROJECT", "TEST"),
        confluence_space=os.getenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", "~user@example.com"),
        bitbucket_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", "~example_user"),
        bitbucket_create_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT", "EXAMPLE"),
        bitbucket_repo=os.getenv("ATLASSIAN_E2E_BITBUCKET_REPO", "example-e2e-repo"),
    )
```

Create `tests/e2e/support/runner.py` with:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.e2e.support.env import LiveEnv

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def run_cli(live_env: LiveEnv, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{SRC_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(SRC_ROOT)
    command = [
        sys.executable,
        "-m",
        "atlassian_cli.main",
        "--config-file",
        str(live_env.config_file),
        *args,
    ]
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def run_json(live_env: LiveEnv, *args: str):
    result = run_cli(live_env, *args)
    if result.returncode != 0:
        raise AssertionError(
            "CLI command failed\n"
            f"command: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)


def run_failure(live_env: LiveEnv, *args: str, expected: str) -> str:
    result = run_cli(live_env, *args)
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0:
        raise AssertionError(f"command unexpectedly succeeded: {' '.join(args)}")
    assert expected in combined
    return combined
```

Create `tests/e2e/support/cleanup.py` with:

```python
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CleanupRegistry:
    callbacks: list[tuple[str, Callable[[], None]]] = field(default_factory=list)

    def add(self, label: str, callback: Callable[[], None]) -> None:
        self.callbacks.append((label, callback))

    def run(self) -> None:
        errors: list[str] = []
        while self.callbacks:
            label, callback = self.callbacks.pop()
            try:
                callback()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        if errors:
            raise AssertionError("cleanup failed\n" + "\n".join(errors))
```

Create `tests/e2e/support/names.py` with:

```python
from datetime import UTC, datetime
from uuid import uuid4


def unique_name(prefix: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}-{uuid4().hex[:8]}"
```

Create `tests/e2e/support/context.py` with:

```python
import os

from atlassian_cli.config.loader import load_config
from atlassian_cli.config.models import Product, RuntimeOverrides
from atlassian_cli.config.resolver import resolve_runtime_context
from atlassian_cli.products.factory import build_provider
from tests.e2e.support.env import LiveEnv


def build_live_context(product: Product, live_env: LiveEnv):
    config = load_config(live_env.config_file)
    product_config = config.product_config(product)
    if product_config is None:
        raise AssertionError(f"missing [{product.value}] config in {live_env.config_file}")
    profile = product_config.to_profile_config(product=product, name=product.value)
    return resolve_runtime_context(
        profile=profile,
        env=dict(os.environ),
        default_headers=config.headers,
        overrides=RuntimeOverrides(product=product, output="json"),
    )


def build_live_provider(product: Product, live_env: LiveEnv):
    return build_provider(build_live_context(product, live_env))
```

Create `tests/e2e/support/git.py` with:

```python
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitSandbox:
    root: Path

    @classmethod
    def clone(cls, clone_url: str, destination: Path) -> "GitSandbox":
        subprocess.run(
            ["git", "clone", clone_url, str(destination)],
            check=True,
            capture_output=True,
            text=True,
        )
        return cls(root=destination)

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def configure_identity(self) -> None:
        self.run("config", "user.name", "atlassian-cli-e2e")
        self.run("config", "user.email", "atlassian-cli-e2e@example.com")

    def create_commit(self, branch: str, file_name: str, content: str, message: str) -> None:
        self.run("checkout", "-b", branch)
        (self.root / file_name).write_text(content)
        self.run("add", file_name)
        self.run("commit", "-m", message)

    def push(self, branch: str) -> None:
        self.run("push", "-u", "origin", branch)

    def delete_remote_branch(self, branch: str) -> None:
        self.run("push", "origin", "--delete", branch)
```

Create `tests/e2e/support/__init__.py` with:

```python
from tests.e2e.support.cleanup import CleanupRegistry
from tests.e2e.support.context import build_live_context, build_live_provider
from tests.e2e.support.env import LiveEnv, load_live_env
from tests.e2e.support.git import GitSandbox
from tests.e2e.support.names import unique_name
from tests.e2e.support.runner import run_cli, run_failure, run_json

__all__ = [
    "CleanupRegistry",
    "GitSandbox",
    "LiveEnv",
    "build_live_context",
    "build_live_provider",
    "load_live_env",
    "run_cli",
    "run_failure",
    "run_json",
    "unique_name",
]
```

Create `tests/e2e/conftest.py` with:

```python
import pytest

from tests.e2e.support import LiveEnv, load_live_env


@pytest.fixture(scope="session")
def live_env() -> LiveEnv:
    try:
        return load_live_env()
    except RuntimeError as exc:
        pytest.skip(str(exc))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/e2e/test_support.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/support/__init__.py tests/e2e/support/cleanup.py tests/e2e/support/context.py tests/e2e/support/env.py tests/e2e/support/git.py tests/e2e/support/names.py tests/e2e/support/runner.py tests/e2e/test_support.py
git commit -m "test: add live e2e support helpers"
```

## Task 4: Add The Coverage Manifest And Command-Surface Guard

**Files:**
- Create: `tests/e2e/coverage_manifest.py`
- Create: `tests/e2e/test_coverage_manifest.py`
- Test: `tests/e2e/test_coverage_manifest.py`

- [ ] **Step 1: Write the failing manifest test**

Create `tests/e2e/test_coverage_manifest.py` with:

```python
from typer.main import get_command

from atlassian_cli.cli import app
from tests.e2e.coverage_manifest import COVERAGE_MANIFEST


def discover_leaf_commands() -> set[str]:
    root = get_command(app)
    commands: set[str] = set()
    for product_name, product_cmd in root.commands.items():
        for group_name, group_cmd in product_cmd.commands.items():
            for leaf_name in getattr(group_cmd, "commands", {}):
                commands.add(f"{product_name} {group_name} {leaf_name}")
    return commands


def test_coverage_manifest_matches_cli_surface() -> None:
    assert set(COVERAGE_MANIFEST) == discover_leaf_commands()


def test_coverage_manifest_declares_owners_for_every_command() -> None:
    assert all(owner for owner in COVERAGE_MANIFEST.values())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py -v`

Expected: FAIL because `tests/e2e/coverage_manifest.py` does not exist yet.

- [ ] **Step 3: Write the manifest**

Create `tests/e2e/coverage_manifest.py` with:

```python
COVERAGE_MANIFEST = {
    "jira issue get": "test_jira_issue_round_trip_live",
    "jira issue search": "test_jira_issue_round_trip_live",
    "jira issue create": "test_jira_issue_round_trip_live",
    "jira issue update": "test_jira_issue_round_trip_live",
    "jira issue transition": "test_jira_issue_round_trip_live",
    "jira issue transitions": "test_jira_issue_round_trip_live",
    "jira issue delete": "test_jira_issue_round_trip_live",
    "jira issue batch-create": "test_jira_issue_batch_create_live",
    "jira issue changelog-batch": "test_jira_issue_changelog_batch_rejected_live",
    "jira field search": "test_jira_project_and_metadata_live",
    "jira field options": "test_jira_project_and_metadata_live",
    "jira comment add": "test_jira_issue_round_trip_live",
    "jira comment edit": "test_jira_issue_round_trip_live",
    "jira project list": "test_jira_project_and_metadata_live",
    "jira project get": "test_jira_project_and_metadata_live",
    "jira user get": "test_jira_project_and_metadata_live",
    "jira user search": "test_jira_project_and_metadata_live",
    "confluence page get": "test_confluence_page_round_trip_live",
    "confluence page search": "test_confluence_space_and_search_live",
    "confluence page children": "test_confluence_page_move_and_children_live",
    "confluence page tree": "test_confluence_space_and_search_live",
    "confluence page history": "test_confluence_page_round_trip_live",
    "confluence page diff": "test_confluence_page_round_trip_live",
    "confluence page move": "test_confluence_page_move_and_children_live",
    "confluence page create": "test_confluence_page_round_trip_live",
    "confluence page update": "test_confluence_page_round_trip_live",
    "confluence page delete": "test_confluence_page_round_trip_live",
    "confluence comment list": "test_confluence_comment_round_trip_live",
    "confluence comment add": "test_confluence_comment_round_trip_live",
    "confluence comment reply": "test_confluence_comment_round_trip_live",
    "confluence space list": "test_confluence_space_and_search_live",
    "confluence space get": "test_confluence_space_and_search_live",
    "confluence attachment list": "test_confluence_attachment_round_trip_live",
    "confluence attachment upload": "test_confluence_attachment_round_trip_live",
    "confluence attachment download": "test_confluence_attachment_round_trip_live",
    "bitbucket project list": "test_bitbucket_project_and_repo_queries_live",
    "bitbucket project get": "test_bitbucket_project_and_repo_queries_live",
    "bitbucket repo get": "test_bitbucket_project_and_repo_queries_live",
    "bitbucket repo list": "test_bitbucket_project_and_repo_queries_live",
    "bitbucket repo create": "test_bitbucket_repo_create_live",
    "bitbucket branch list": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr list": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr get": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr create": "test_bitbucket_branch_and_pr_round_trip_live",
    "bitbucket pr merge": "test_bitbucket_branch_and_pr_round_trip_live",
}
```

- [ ] **Step 4: Run the manifest tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/coverage_manifest.py tests/e2e/test_coverage_manifest.py
git commit -m "test: add e2e coverage manifest"
```

## Task 5: Add Jira Live E2E Coverage

**Files:**
- Create: `tests/e2e/test_jira_live.py`
- Test: `tests/e2e/test_jira_live.py`

- [ ] **Step 1: Write the failing Jira live tests**

Create `tests/e2e/test_jira_live.py` with:

```python
import json

import pytest

from tests.e2e.support import CleanupRegistry, run_failure, run_json, unique_name

pytestmark = pytest.mark.e2e


def test_jira_project_and_metadata_live(live_env) -> None:
    projects = run_json(live_env, "jira", "project", "list", "--output", "json")
    assert any(item["key"] == live_env.jira_project for item in projects["results"])

    project = run_json(
        live_env,
        "jira",
        "project",
        "get",
        live_env.jira_project,
        "--output",
        "json",
    )
    assert project["key"] == live_env.jira_project

    fields = run_json(live_env, "jira", "field", "search", "--query", "", "--output", "json")
    assert fields["results"]

    option_field = None
    option_result = None
    for field in fields["results"]:
        if not field.get("id"):
            continue
        candidate = run_json(
            live_env,
            "jira",
            "field",
            "options",
            field["id"],
            "--project",
            live_env.jira_project,
            "--issue-type",
            "Task",
            "--output",
            "json",
        )
        if candidate["results"]:
            option_field = field
            option_result = candidate
            break

    if option_field is None or option_result is None:
        pytest.skip("no Jira field with allowedValues was discoverable for TEST Task")

    assert option_result["results"]

    users = run_json(live_env, "jira", "user", "search", "--query", "a", "--output", "raw-json")
    user_name = next((item.get("name") for item in users if item.get("name")), None)
    if user_name is None:
        pytest.skip("no Jira user with a name field was discoverable")

    user = run_json(live_env, "jira", "user", "get", user_name, "--output", "json")
    assert user["name"] == user_name


def test_jira_issue_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    summary = unique_name("jira-e2e")
    issue_key = None
    try:
        created = run_json(
            live_env,
            "jira",
            "issue",
            "create",
            "--project",
            live_env.jira_project,
            "--issue-type",
            "Task",
            "--summary",
            summary,
            "--description",
            "created by live e2e",
            "--output",
            "json",
        )
        issue_key = created["key"]
        registry.add(
            f"jira issue delete {issue_key}",
            lambda: run_json(
                live_env,
                "jira",
                "issue",
                "delete",
                issue_key,
                "--yes",
                "--output",
                "json",
            ),
        )

        fetched = run_json(live_env, "jira", "issue", "get", issue_key, "--output", "json")
        assert fetched["key"] == issue_key

        updated_summary = f"{summary}-updated"
        updated = run_json(
            live_env,
            "jira",
            "issue",
            "update",
            issue_key,
            "--summary",
            updated_summary,
            "--description",
            "updated by live e2e",
            "--output",
            "json",
        )
        assert updated["updated"] is True

        search = run_json(
            live_env,
            "jira",
            "issue",
            "search",
            "--jql",
            f'project = {live_env.jira_project} AND summary ~ "{updated_summary}"',
            "--output",
            "json",
        )
        assert any(item["key"] == issue_key for item in search["issues"])

        transitions = run_json(
            live_env,
            "jira",
            "issue",
            "transitions",
            issue_key,
            "--output",
            "json",
        )
        assert transitions["results"]
        transition_name = next(
            (item.get("name") for item in transitions["results"] if item.get("name")),
            None,
        )
        if transition_name is not None:
            transitioned = run_json(
                live_env,
                "jira",
                "issue",
                "transition",
                issue_key,
                "--to",
                transition_name,
                "--output",
                "json",
            )
            assert transitioned["transition"] == transition_name

        comment = run_json(
            live_env,
            "jira",
            "comment",
            "add",
            issue_key,
            "--body",
            "first comment",
            "--output",
            "json",
        )
        assert comment["id"]

        edited = run_json(
            live_env,
            "jira",
            "comment",
            "edit",
            issue_key,
            comment["id"],
            "--body",
            "edited comment",
            "--output",
            "json",
        )
        assert edited["id"] == comment["id"]
    finally:
        registry.run()


def test_jira_issue_batch_create_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    payload = [
        {
            "project": {"key": live_env.jira_project},
            "issuetype": {"name": "Task"},
            "summary": unique_name("jira-batch-one"),
        },
        {
            "project": {"key": live_env.jira_project},
            "issuetype": {"name": "Task"},
            "summary": unique_name("jira-batch-two"),
        },
    ]
    batch_file = tmp_path / "issues.json"
    batch_file.write_text(json.dumps(payload))
    try:
        result = run_json(
            live_env,
            "jira",
            "issue",
            "batch-create",
            "--file",
            str(batch_file),
            "--output",
            "json",
        )
        keys = [item["key"] for item in result["issues"] if item.get("key")]
        assert len(keys) == 2
        for key in keys:
            registry.add(
                f"jira issue delete {key}",
                lambda key=key: run_json(
                    live_env,
                    "jira",
                    "issue",
                    "delete",
                    key,
                    "--yes",
                    "--output",
                    "json",
                ),
            )
    finally:
        registry.run()


def test_jira_issue_changelog_batch_rejected_live(live_env) -> None:
    output = run_failure(
        live_env,
        "jira",
        "issue",
        "changelog-batch",
        "--issue",
        "TEST-1",
        expected="Cloud support is not available in v1",
    )
    assert "Cloud support is not available in v1" in output
```

- [ ] **Step 2: Run the Jira live tests to verify they fail**

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_jira_live.py -m e2e -v`

Expected: FAIL because the Jira live test file does not exist yet and the support layer has not been exercised against the real instance.

- [ ] **Step 3: Write the minimal implementation**

Create `tests/e2e/test_jira_live.py` exactly as shown in Step 1.

- [ ] **Step 4: Run the Jira live tests to verify they pass**

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_jira_live.py -m e2e -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_jira_live.py
git commit -m "test: add jira live e2e coverage"
```

## Task 6: Replace The Ad-Hoc Confluence E2E Test With Full Product Coverage

**Files:**
- Create: `tests/e2e/test_confluence_live.py`
- Delete: `tests/e2e/test_live_cli.py`
- Test: `tests/e2e/test_confluence_live.py`

- [ ] **Step 1: Write the failing Confluence live tests**

Create `tests/e2e/test_confluence_live.py` with:

```python
from pathlib import Path

import pytest

from tests.e2e.support import CleanupRegistry, run_json, unique_name

pytestmark = pytest.mark.e2e


def _delete_page(live_env, page_id: str) -> None:
    run_json(
        live_env,
        "confluence",
        "page",
        "delete",
        page_id,
        "--yes",
        "--output",
        "json",
    )


def test_confluence_space_and_search_live(live_env) -> None:
    spaces = run_json(live_env, "confluence", "space", "list", "--output", "json")
    assert any(item["key"] == live_env.confluence_space for item in spaces["results"])

    space = run_json(
        live_env,
        "confluence",
        "space",
        "get",
        live_env.confluence_space,
        "--output",
        "json",
    )
    assert space["key"] == live_env.confluence_space

    registry = CleanupRegistry()
    page_id = None
    try:
        title = unique_name("confluence-search")
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            title,
            "--body",
            "<p>search target</p>",
            "--output",
            "json",
        )
        page_id = created["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        search = run_json(
            live_env,
            "confluence",
            "page",
            "search",
            "--query",
            title,
            "--output",
            "json",
        )
        assert any(item["id"] == page_id for item in search["results"])

        tree = run_json(
            live_env,
            "confluence",
            "page",
            "tree",
            live_env.confluence_space,
            "--output",
            "json",
        )
        assert tree["results"]
    finally:
        registry.run()


def test_confluence_page_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        title = unique_name("confluence-page")
        created = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            title,
            "--body",
            "<p>version one</p>",
            "--output",
            "json",
        )
        page_id = created["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        fetched = run_json(
            live_env,
            "confluence",
            "page",
            "get",
            page_id,
            "--output",
            "json",
        )
        assert fetched["id"] == page_id

        updated = run_json(
            live_env,
            "confluence",
            "page",
            "update",
            page_id,
            "--title",
            f"{title} updated",
            "--body",
            "<p>version two</p>",
            "--output",
            "json",
        )
        assert updated["id"] == page_id
        assert updated["version"] >= created["version"]

        history = run_json(
            live_env,
            "confluence",
            "page",
            "history",
            page_id,
            "--version",
            str(updated["version"]),
            "--output",
            "json",
        )
        assert history["id"] == page_id

        diff = run_json(
            live_env,
            "confluence",
            "page",
            "diff",
            page_id,
            "--from-version",
            str(created["version"]),
            "--to-version",
            str(updated["version"]),
            "--output",
            "json",
        )
        assert diff["page_id"] == page_id
        assert diff["from_version"] == created["version"]
        assert diff["to_version"] == updated["version"]
        assert "version two" in diff["diff"] or "+<p>version two</p>" in diff["diff"]
    finally:
        registry.run()


def test_confluence_page_move_and_children_live(live_env) -> None:
    registry = CleanupRegistry()
    parent_id = None
    child_id = None
    try:
        parent = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-parent"),
            "--body",
            "<p>parent</p>",
            "--output",
            "json",
        )
        parent_id = parent["id"]
        registry.add(f"confluence page delete {parent_id}", lambda: _delete_page(live_env, parent_id))

        child = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-child"),
            "--body",
            "<p>child</p>",
            "--output",
            "json",
        )
        child_id = child["id"]
        registry.add(f"confluence page delete {child_id}", lambda: _delete_page(live_env, child_id))

        moved = run_json(
            live_env,
            "confluence",
            "page",
            "move",
            child_id,
            "--parent",
            parent_id,
            "--output",
            "json",
        )
        assert moved["id"] == child_id

        children = run_json(
            live_env,
            "confluence",
            "page",
            "children",
            parent_id,
            "--output",
            "json",
        )
        assert any(item["id"] == child_id for item in children["results"])
    finally:
        registry.run()


def test_confluence_comment_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-comment"),
            "--body",
            "<p>comment page</p>",
            "--output",
            "json",
        )
        page_id = page["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        comment = run_json(
            live_env,
            "confluence",
            "comment",
            "add",
            page_id,
            "--body",
            "top-level comment",
            "--output",
            "json",
        )
        assert comment["id"]

        reply = run_json(
            live_env,
            "confluence",
            "comment",
            "reply",
            comment["id"],
            "--body",
            "reply comment",
            "--output",
            "json",
        )
        assert reply["id"]

        comments = run_json(
            live_env,
            "confluence",
            "comment",
            "list",
            page_id,
            "--output",
            "json",
        )
        bodies = [item.get("body", "") for item in comments["results"]]
        assert any("top-level comment" in body for body in bodies)
    finally:
        registry.run()


def test_confluence_attachment_round_trip_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    page_id = None
    try:
        page = run_json(
            live_env,
            "confluence",
            "page",
            "create",
            "--space",
            live_env.confluence_space,
            "--title",
            unique_name("confluence-attachment"),
            "--body",
            "<p>attachment page</p>",
            "--output",
            "json",
        )
        page_id = page["id"]
        registry.add(f"confluence page delete {page_id}", lambda: _delete_page(live_env, page_id))

        upload_file = tmp_path / "deploy.log"
        upload_file.write_text("release=42\nstatus=ok\n")

        uploaded = run_json(
            live_env,
            "confluence",
            "attachment",
            "upload",
            page_id,
            "--file",
            str(upload_file),
            "--output",
            "json",
        )
        assert uploaded["id"]

        listed = run_json(
            live_env,
            "confluence",
            "attachment",
            "list",
            page_id,
            "--output",
            "json",
        )
        attachment = next(item for item in listed["results"] if item["id"] == uploaded["id"])

        download_target = tmp_path / "downloaded.log"
        downloaded = run_json(
            live_env,
            "confluence",
            "attachment",
            "download",
            attachment["id"],
            "--destination",
            str(download_target),
            "--output",
            "json",
        )
        assert Path(downloaded["path"]).read_text() == "release=42\nstatus=ok\n"
    finally:
        registry.run()
```

- [ ] **Step 2: Run the Confluence live tests to verify they fail**

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_confluence_live.py -m e2e -v`

Expected: FAIL because the full Confluence live suite does not exist yet and `tests/e2e/test_live_cli.py` is still the only partial e2e test.

- [ ] **Step 3: Write the minimal implementation**

Create `tests/e2e/test_confluence_live.py` exactly as shown in Step 1 and delete `tests/e2e/test_live_cli.py`.

- [ ] **Step 4: Run the Confluence live tests to verify they pass**

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_confluence_live.py -m e2e -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_confluence_live.py tests/e2e/test_live_cli.py
git commit -m "test: add confluence live e2e coverage"
```

## Task 7: Add Bitbucket Git Sandbox Helpers And Live Coverage

**Files:**
- Create: `tests/e2e/test_bitbucket_live.py`
- Modify: `tests/e2e/support/context.py`
- Modify: `tests/e2e/support/git.py`
- Test: `tests/e2e/test_bitbucket_live.py`

- [ ] **Step 1: Write the failing Bitbucket live tests**

Create `tests/e2e/test_bitbucket_live.py` with:

```python
from pathlib import Path

import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support import CleanupRegistry, GitSandbox, build_live_provider, run_json, unique_name

pytestmark = pytest.mark.e2e


def _delete_repo(live_env, repo_slug: str) -> None:
    provider = build_live_provider(Product.BITBUCKET, live_env)
    provider.client.delete_repo(live_env.bitbucket_project, repo_slug)


def test_bitbucket_project_and_repo_queries_live(live_env) -> None:
    projects = run_json(live_env, "bitbucket", "project", "list", "--output", "json")
    assert any(item["key"] == live_env.bitbucket_project for item in projects["results"])

    project = run_json(
        live_env,
        "bitbucket",
        "project",
        "get",
        live_env.bitbucket_project,
        "--output",
        "json",
    )
    assert project["key"] == live_env.bitbucket_project

    repos = run_json(
        live_env,
        "bitbucket",
        "repo",
        "list",
        "--project",
        live_env.bitbucket_project,
        "--output",
        "json",
    )
    assert any(item["slug"] == live_env.bitbucket_repo for item in repos["results"])

    repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--output",
        "json",
    )
    assert repo["slug"] == live_env.bitbucket_repo


def test_bitbucket_repo_create_live(live_env) -> None:
    registry = CleanupRegistry()
    repo_name = unique_name("atlassian-cli-e2e-repo")
    repo_slug = None
    try:
        created = run_json(
            live_env,
            "bitbucket",
            "repo",
            "create",
            "--project",
            live_env.bitbucket_project,
            "--name",
            repo_name,
            "--output",
            "json",
        )
        repo_slug = created["slug"]
        registry.add(f"bitbucket repo delete {repo_slug}", lambda: _delete_repo(live_env, repo_slug))
        assert created["name"] == repo_name
    finally:
        registry.run()


def test_bitbucket_branch_and_pr_round_trip_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    raw_repo = run_json(
        live_env,
        "bitbucket",
        "repo",
        "get",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--output",
        "raw-json",
    )
    clone_links = raw_repo.get("links", {}).get("clone", [])
    clone_url = next(link["href"] for link in clone_links if link.get("name") == "http")
    default_branch = raw_repo.get("defaultBranch", {}).get("displayId") or "main"

    branch_name = unique_name("e2e-branch")
    sandbox_path = tmp_path / "repo"
    sandbox = GitSandbox.clone(clone_url, sandbox_path)
    sandbox.configure_identity()
    sandbox.create_commit(
        branch_name,
        "e2e-note.txt",
        f"{branch_name}\n",
        f"test: add {branch_name}",
    )
    sandbox.push(branch_name)
    registry.add(
        f"bitbucket branch delete {branch_name}",
        lambda: sandbox.delete_remote_branch(branch_name),
    )

    branches = run_json(
        live_env,
        "bitbucket",
        "branch",
        "list",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--filter",
        branch_name,
        "--output",
        "json",
    )
    assert any(item["display_id"] == branch_name for item in branches["results"])

    created_pr = run_json(
        live_env,
        "bitbucket",
        "pr",
        "create",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--title",
        unique_name("e2e-pr"),
        "--description",
        "created by live e2e",
        "--from-ref",
        f"refs/heads/{branch_name}",
        "--to-ref",
        f"refs/heads/{default_branch}",
        "--output",
        "json",
    )
    pr_id = created_pr["id"]

    listed = run_json(
        live_env,
        "bitbucket",
        "pr",
        "list",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        "--state",
        "OPEN",
        "--output",
        "json",
    )
    assert any(item["id"] == pr_id for item in listed["results"])

    fetched = run_json(
        live_env,
        "bitbucket",
        "pr",
        "get",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        str(pr_id),
        "--output",
        "json",
    )
    assert fetched["id"] == pr_id

    merged = run_json(
        live_env,
        "bitbucket",
        "pr",
        "merge",
        live_env.bitbucket_project,
        live_env.bitbucket_repo,
        str(pr_id),
        "--output",
        "json",
    )
    assert merged["id"] == pr_id
    assert merged["state"] == "MERGED"
```

- [ ] **Step 2: Run the Bitbucket live tests to verify they fail**

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_bitbucket_live.py -m e2e -v`

Expected: FAIL because the Bitbucket live suite and supporting delete/clone helpers are not finished yet.

- [ ] **Step 3: Write the minimal implementation**

Create `tests/e2e/test_bitbucket_live.py` exactly as shown in Step 1.

If `GitSandbox.delete_remote_branch()` needs to tolerate already-deleted branches, update `tests/e2e/support/git.py` to:

```python
    def delete_remote_branch(self, branch: str) -> None:
        result = subprocess.run(
            ["git", "push", "origin", "--delete", branch],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and "remote ref does not exist" not in result.stderr.lower():
            raise AssertionError(result.stderr.strip() or result.stdout.strip())
```

- [ ] **Step 4: Run the Bitbucket live tests to verify they pass**

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_bitbucket_live.py -m e2e -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_bitbucket_live.py tests/e2e/support/context.py tests/e2e/support/git.py
git commit -m "test: add bitbucket live e2e coverage"
```

## Task 8: Refresh README And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Test: `tests/test_readme.py`
- Test: `tests/test_cli_help.py`
- Test: `tests/integration/test_smoke.py`

- [ ] **Step 1: Write the failing docs contract tests**

Replace the e2e-specific assertions in `tests/test_readme.py` with:

```python
def test_readme_mentions_full_local_e2e_suite() -> None:
    readme = Path("README.md").read_text()

    assert "tests/e2e/test_jira_live.py" in readme
    assert "tests/e2e/test_confluence_live.py" in readme
    assert "tests/e2e/test_bitbucket_live.py" in readme
    assert "ATLASSIAN_E2E=1" in readme
    assert "ATLASSIAN_E2E_JIRA_PROJECT" in readme
    assert "ATLASSIAN_E2E_CONFLUENCE_SPACE" in readme
    assert "ATLASSIAN_E2E_BITBUCKET_PROJECT" in readme
    assert "ATLASSIAN_E2E_BITBUCKET_REPO" in readme
    assert "real writes" in readme.lower()
```

- [ ] **Step 2: Run the docs contract tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_readme.py -v`

Expected: FAIL because the README still describes only the earlier partial local e2e note and write flag.

- [ ] **Step 3: Update the docs**

Replace the local e2e section in `README.md` with:

```markdown
## Local e2e testing

The repository includes a local-only live e2e suite that covers every CLI subcommand with at least one real command chain.

Live test modules:

- `tests/e2e/test_jira_live.py`
- `tests/e2e/test_confluence_live.py`
- `tests/e2e/test_bitbucket_live.py`
- `tests/e2e/test_coverage_manifest.py`

The suite shells out through `python -m atlassian_cli.main`, reuses your normal CLI config, and performs real writes against the configured Atlassian instances.

Environment:

- `ATLASSIAN_E2E=1`
- `ATLASSIAN_CONFIG_FILE=/path/to/config.toml` (optional)
- `ATLASSIAN_E2E_JIRA_PROJECT=TEST`
- `ATLASSIAN_E2E_CONFLUENCE_SPACE='~user@example.com'`
- `ATLASSIAN_E2E_BITBUCKET_PROJECT='~example_user'`
- `ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT=EXAMPLE`
- `ATLASSIAN_E2E_BITBUCKET_REPO=example-e2e-repo`

Recommended runs:

```bash
ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py tests/e2e/test_jira_live.py tests/e2e/test_confluence_live.py tests/e2e/test_bitbucket_live.py -m e2e -v
```

The live suite performs real writes and best-effort cleanup for Jira issues, Confluence pages/comments/attachments, Bitbucket repositories, branches, and pull requests. If cleanup fails, the tests should print residue identifiers for manual removal.
```

- [ ] **Step 4: Run the docs and verification suite**

Run: `.venv/bin/python -m pytest tests/test_readme.py tests/test_cli_help.py tests/integration/test_smoke.py tests/e2e/test_support.py tests/e2e/test_coverage_manifest.py tests/products/confluence/test_provider.py tests/products/confluence/test_attachment_service.py tests/products/confluence/test_attachment_command.py tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_repo_command.py -v`

Expected: PASS

Run: `ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_jira_live.py tests/e2e/test_confluence_live.py tests/e2e/test_bitbucket_live.py -m e2e -v`

Expected: PASS

Run: `.venv/bin/ruff check src tests`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: describe full local e2e coverage suite"
```
