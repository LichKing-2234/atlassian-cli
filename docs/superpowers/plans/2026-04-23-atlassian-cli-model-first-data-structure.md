# Atlassian CLI Model-First Data Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CLI's thin schema and service-level dictionary shaping with model-first Jira, Confluence, and Bitbucket resource parsing and normalized output, while keeping the current command surface and raw output modes.

**Architecture:** Add a shared `ApiModel` base plus lightweight normalization helpers, change providers to expose raw SDK payloads where the current wrappers strip useful metadata, and move resource shaping into product `schemas.py` via `from_api_response()` and `to_simplified_dict()`. Services become orchestration layers that branch between raw and normalized output, and the renderer stays generic while learning how to display sparse row sets and collection envelopes for table output.

**Tech Stack:** Python 3.13, Typer, Pydantic v2, atlassian-python-api, rich, pytest

---

## Planned File Structure

### Create

- `src/atlassian_cli/models/__init__.py`
- `src/atlassian_cli/models/base.py`
- `src/atlassian_cli/models/common.py`
- `tests/models/test_base.py`
- `tests/test_readme.py`
- `tests/products/jira/test_schemas.py`
- `tests/products/jira/test_project_command.py`
- `tests/products/jira/test_user_command.py`
- `tests/products/confluence/test_schemas.py`
- `tests/products/confluence/test_space_command.py`
- `tests/products/bitbucket/test_schemas.py`
- `tests/products/bitbucket/test_pr_command.py`

### Modify

- `src/atlassian_cli/output/renderers.py`
- `src/atlassian_cli/products/jira/schemas.py`
- `src/atlassian_cli/products/jira/services/issue.py`
- `src/atlassian_cli/products/jira/services/project.py`
- `src/atlassian_cli/products/jira/services/user.py`
- `src/atlassian_cli/products/jira/providers/base.py`
- `src/atlassian_cli/products/jira/providers/server.py`
- `src/atlassian_cli/products/confluence/schemas.py`
- `src/atlassian_cli/products/confluence/services/page.py`
- `src/atlassian_cli/products/confluence/services/space.py`
- `src/atlassian_cli/products/confluence/services/attachment.py`
- `src/atlassian_cli/products/confluence/providers/base.py`
- `src/atlassian_cli/products/confluence/providers/server.py`
- `src/atlassian_cli/products/bitbucket/schemas.py`
- `src/atlassian_cli/products/bitbucket/services/project.py`
- `src/atlassian_cli/products/bitbucket/services/repo.py`
- `src/atlassian_cli/products/bitbucket/services/branch.py`
- `src/atlassian_cli/products/bitbucket/services/pr.py`
- `src/atlassian_cli/products/bitbucket/providers/base.py`
- `src/atlassian_cli/products/bitbucket/providers/server.py`
- `tests/output/test_renderers.py`
- `tests/products/jira/test_issue_service.py`
- `tests/products/jira/test_project_service.py`
- `tests/products/confluence/test_page_service.py`
- `tests/products/confluence/test_space_service.py`
- `tests/products/bitbucket/test_pr_service.py`
- `tests/products/bitbucket/test_repo_service.py`
- `tests/products/bitbucket/test_provider.py`
- `tests/products/test_header_providers.py`
- `README.md`
- `tests/integration/test_smoke.py`

### Responsibility Notes

- `src/atlassian_cli/models/base.py` owns the reusable `ApiModel` contract and timestamp helpers used by all product resource models.
- `src/atlassian_cli/models/common.py` owns lightweight normalization helpers such as string coercion, nested lookup, and minimal ADF text extraction so product models do not repeat low-level parsing logic.
- Product `schemas.py` files own resource parsing and normalized serialization. After this refactor, services should stop building nested dictionaries manually.
- Product `services/*.py` modules own raw-versus-normalized branching and resource operation orchestration, including collection envelope assembly and Bitbucket merge prefetch behavior.
- Product `providers/base.py` files own the full typed contract surface consumed by services, and `providers/server.py` files own raw SDK interaction without output shaping.
- `output/renderers.py` stays generic but learns how to render sparse row sets and collection envelopes for table output without knowing any product-specific field names.
- The plan must preserve the current dirty-worktree provider constructor direction (`auth_mode`, PAT token wiring, and injected headers). Do not revert or work around those changes by reintroducing the older provider signatures.

### Common Commands

- Shared model tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/models/test_base.py -v`
- Renderer tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/output/test_renderers.py -v`
- Jira tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/jira -v`
- Confluence tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/confluence -v`
- Bitbucket tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/bitbucket -v`
- Cross-product provider tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/test_factory.py tests/products/test_header_providers.py -v`
- Smoke tests: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/integration/test_smoke.py -v`
- Full suite: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest -q`

## Task 1: Add Shared Model Primitives And Generic Table Rendering

**Files:**
- Create: `src/atlassian_cli/models/__init__.py`
- Create: `src/atlassian_cli/models/base.py`
- Create: `src/atlassian_cli/models/common.py`
- Create: `tests/models/test_base.py`
- Modify: `src/atlassian_cli/output/renderers.py`
- Modify: `tests/output/test_renderers.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.models.base import ApiModel, TimestampMixin


class DemoModel(ApiModel):
    id: str
    name: str
    optional: str | None = None

    @classmethod
    def from_api_response(cls, data, **kwargs):
        return cls(id=str(data["id"]), name=data["name"], optional=data.get("optional"))


def test_api_model_to_simplified_dict_excludes_none() -> None:
    model = DemoModel.from_api_response({"id": 7, "name": "demo"})

    assert model.to_simplified_dict() == {"id": "7", "name": "demo"}


def test_timestamp_mixin_formats_server_timestamp() -> None:
    formatted = TimestampMixin.format_timestamp("2026-04-23T09:15:00.000+0000")

    assert formatted == "2026-04-23 09:15:00"
```

```python
from atlassian_cli.output.renderers import render_output


def test_render_output_table_uses_results_envelope_rows() -> None:
    payload = {
        "start_at": 0,
        "max_results": 2,
        "results": [
            {"key": "OPS-1", "summary": "First"},
            {"key": "OPS-2", "summary": "Second", "assignee": {"display_name": "Alice"}},
        ],
    }

    rendered = render_output(payload, output="table")

    assert "OPS-1" in rendered
    assert "OPS-2" in rendered
    assert "assignee" in rendered.lower()


def test_render_output_table_unions_columns_across_sparse_rows() -> None:
    payload = [
        {"key": "OPS-1", "summary": "First"},
        {"key": "OPS-2", "summary": "Second", "priority": {"name": "High"}},
    ]

    rendered = render_output(payload, output="table")

    assert "priority" in rendered.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/models/test_base.py tests/output/test_renderers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlassian_cli.models'` and failing renderer assertions because the current table logic only uses the first row's keys and does not understand collection envelopes.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/atlassian_cli/models/__init__.py
from .base import ApiModel, TimestampMixin

__all__ = ["ApiModel", "TimestampMixin"]
```

```python
# src/atlassian_cli/models/base.py
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound="ApiModel")


class ApiModel(BaseModel):
    @classmethod
    def from_api_response(cls: type[T], data: dict[str, Any] | None, **kwargs: Any) -> T:
        raise NotImplementedError

    def to_simplified_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class TimestampMixin:
    @staticmethod
    def format_timestamp(value: str | None) -> str | None:
        if not value:
            return None
        candidate = value.replace("Z", "+00:00")
        if "+" in candidate and ":" not in candidate[-5:]:
            pos = candidate.rfind("+")
            candidate = f"{candidate[: pos + 3]}:{candidate[pos + 3:]}"
        elif "-" in candidate[10:] and ":" not in candidate[-5:]:
            pos = candidate.rfind("-")
            candidate = f"{candidate[: pos + 3]}:{candidate[pos + 3:]}"
        try:
            return datetime.fromisoformat(candidate).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value
```

```python
# src/atlassian_cli/models/common.py
from typing import Any


def coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def nested_get(data: dict[str, Any] | None, *path: str) -> Any:
    current: Any = data or {}
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def adf_to_text(node: Any) -> str:
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text", ""))
    return "".join(adf_to_text(child) for child in node.get("content", []))
```

```python
# src/atlassian_cli/output/renderers.py
from io import StringIO

from rich.console import Console
from rich.table import Table

from atlassian_cli.output.formatters import to_json, to_yaml
from atlassian_cli.output.modes import normalized_output


def _extract_table_rows(value) -> list[dict]:
    if isinstance(value, dict):
        for key in ("results", "issues"):
            candidate = value.get(key)
            if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
                return candidate
        return [value]
    if isinstance(value, list):
        return value
    return [value]


def render_output(value, *, output: str) -> str:
    output = normalized_output(output)
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)

    rows = _extract_table_rows(value)
    if not rows:
        return ""

    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)

    table = Table()
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*[str(row.get(column, "")) for column in columns])

    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120)
    console.print(table)
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/models/test_base.py tests/output/test_renderers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/models/__init__.py src/atlassian_cli/models/base.py src/atlassian_cli/models/common.py src/atlassian_cli/output/renderers.py tests/models/test_base.py tests/output/test_renderers.py
git commit -m "refactor: add shared api models and generic table envelopes"
```

## Task 2: Return Raw Provider Payloads And Expand Provider Contracts

**Files:**
- Modify: `src/atlassian_cli/products/jira/providers/base.py`
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Modify: `src/atlassian_cli/products/confluence/providers/base.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `tests/products/test_header_providers.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.confluence.providers.server import ConfluenceServerProvider
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def test_jira_provider_search_issues_returns_full_search_payload(monkeypatch) -> None:
    class FakeJira:
        def __init__(self, **kwargs):
            self._session = object()

        def jql(self, jql: str, start: int, limit: int) -> dict:
            return {
                "total": 2,
                "startAt": start,
                "maxResults": limit,
                "issues": [{"key": "OPS-1"}, {"key": "OPS-2"}],
            }

    monkeypatch.setattr("atlassian_cli.products.jira.providers.server.Jira", FakeJira)
    monkeypatch.setattr(
        "atlassian_cli.products.jira.providers.server.patch_session_headers",
        lambda session, headers: None,
    )

    provider = JiraServerProvider(
        url="https://jira.example.com",
        username="alice",
        password="secret",
        token=None,
        headers={},
    )

    result = provider.search_issues("project = OPS", start=0, limit=2)

    assert result["total"] == 2
    assert [item["key"] for item in result["issues"]] == ["OPS-1", "OPS-2"]


def test_confluence_provider_list_spaces_returns_full_paged_payload(monkeypatch) -> None:
    class FakeConfluence:
        def __init__(self, **kwargs):
            self._session = object()

        def get_all_spaces(self, start: int, limit: int) -> dict:
            return {
                "results": [{"id": 1, "key": "OPS", "name": "Operations"}],
                "start": start,
                "limit": limit,
            }

    monkeypatch.setattr(
        "atlassian_cli.products.confluence.providers.server.Confluence",
        FakeConfluence,
    )
    monkeypatch.setattr(
        "atlassian_cli.products.confluence.providers.server.patch_session_headers",
        lambda session, headers: None,
    )

    provider = ConfluenceServerProvider(
        url="https://confluence.example.com",
        username="alice",
        password="secret",
        token=None,
        headers={},
    )

    result = provider.list_spaces(start=0, limit=25)

    assert result["start"] == 0
    assert result["results"][0]["key"] == "OPS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/test_header_providers.py -v`
Expected: FAIL because `JiraServerProvider.search_issues()` currently strips the search envelope to `["issues"]` and `ConfluenceServerProvider.list_spaces()` currently strips the paged result to `["results"]`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/atlassian_cli/products/jira/providers/base.py
from typing import Protocol


class JiraProvider(Protocol):
    def get_issue(self, issue_key: str) -> dict: ...
    def search_issues(self, jql: str, start: int, limit: int) -> dict: ...
    def create_issue(self, fields: dict) -> dict: ...
    def update_issue(self, issue_key: str, fields: dict) -> dict: ...
    def transition_issue(self, issue_key: str, transition: str) -> dict: ...
    def list_projects(self) -> list[dict]: ...
    def get_project(self, project_key: str) -> dict: ...
    def get_user(self, username: str) -> dict: ...
    def search_users(self, query: str) -> list[dict]: ...
```

```python
# src/atlassian_cli/products/confluence/providers/base.py
from typing import Protocol


class ConfluenceProvider(Protocol):
    def get_page(self, page_id: str) -> dict: ...
    def create_page(self, *, space_key: str, title: str, body: str) -> dict: ...
    def update_page(self, *, page_id: str, title: str, body: str) -> dict: ...
    def delete_page(self, page_id: str) -> dict: ...
    def list_spaces(self, *, start: int, limit: int) -> dict: ...
    def get_space(self, space_key: str) -> dict: ...
    def list_attachments(self, page_id: str) -> dict: ...
    def upload_attachment(self, page_id: str, file_path: str) -> dict: ...
    def download_attachment(self, attachment_id: str, destination: str) -> dict: ...
```

```python
# src/atlassian_cli/products/bitbucket/providers/base.py
from typing import Protocol


class BitbucketProvider(Protocol):
    def list_projects(self, *, start: int, limit: int) -> list[dict]: ...
    def get_project(self, project_key: str) -> dict: ...
    def list_repos(self, *, project_key: str | None, start: int, limit: int) -> list[dict]: ...
    def get_repo(self, project_key: str, repo_slug: str) -> dict: ...
    def create_repo(self, *, project_key: str, name: str, scm_id: str) -> dict: ...
    def list_branches(self, project_key: str, repo_slug: str, filter_text: str | None) -> list[dict]: ...
    def list_pull_requests(self, project_key: str, repo_slug: str, state: str) -> list[dict]: ...
    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict: ...
    def create_pull_request(self, project_key: str, repo_slug: str, payload: dict) -> dict: ...
    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        merge_message: str,
        pr_version: int | None,
    ) -> dict: ...
```

```python
# src/atlassian_cli/products/jira/providers/server.py
def search_issues(self, jql: str, start: int, limit: int) -> dict:
    return self.client.jql(jql, start=start, limit=limit)
```

```python
# src/atlassian_cli/products/confluence/providers/server.py
def list_spaces(self, *, start: int, limit: int) -> dict:
    return self.client.get_all_spaces(start=start, limit=limit)


def list_attachments(self, page_id: str) -> dict:
    return self.client.get_attachments_from_content(page_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/test_header_providers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/providers/base.py src/atlassian_cli/products/jira/providers/server.py src/atlassian_cli/products/confluence/providers/base.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/bitbucket/providers/base.py tests/products/test_header_providers.py
git commit -m "refactor: expose raw provider payload envelopes"
```

## Task 3: Upgrade Jira Schemas To Model-First Resource Parsing

**Files:**
- Modify: `src/atlassian_cli/products/jira/schemas.py`
- Create: `tests/products/jira/test_schemas.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.jira.schemas import JiraIssue, JiraSearchResult, JiraUser


def test_jira_issue_from_api_response_builds_rich_resource() -> None:
    issue = JiraIssue.from_api_response(
        {
            "id": 10001,
            "key": "OPS-1",
            "self": "https://jira.example.com/rest/api/2/issue/10001",
            "fields": {
                "summary": "Broken deploy",
                "description": "Investigate release failure",
                "status": {"name": "Open"},
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alice", "name": "alice"},
                "reporter": {"displayName": "Bob", "name": "bob"},
                "labels": ["release"],
                "project": {"key": "OPS", "name": "Operations"},
                "created": "2026-04-23T09:00:00.000+0000",
                "updated": "2026-04-23T10:00:00.000+0000",
            },
        }
    )

    assert issue.id == "10001"
    assert issue.issue_type.name == "Bug"

    simplified = issue.to_simplified_dict()
    assert simplified["project"]["key"] == "OPS"
    assert simplified["url"] == "https://jira.example.com/rest/api/2/issue/10001"


def test_jira_user_from_api_response_handles_cloud_shape() -> None:
    user = JiraUser.from_api_response(
        {
            "accountId": "abc-123",
            "displayName": "Cloud User",
            "emailAddress": "cloud@example.com",
            "avatarUrls": {"48x48": "https://example.com/avatar.png"},
        }
    )

    simplified = user.to_simplified_dict()

    assert simplified["account_id"] == "abc-123"
    assert simplified["display_name"] == "Cloud User"
    assert simplified["name"] == "Cloud User"


def test_jira_search_result_from_api_response_preserves_metadata() -> None:
    result = JiraSearchResult.from_api_response(
        {
            "total": 2,
            "startAt": 5,
            "maxResults": 2,
            "issues": [
                {"id": 1, "key": "OPS-1", "fields": {"summary": "One", "status": {"name": "Open"}}},
                {"id": 2, "key": "OPS-2", "fields": {"summary": "Two", "status": {"name": "Done"}}},
            ],
        }
    )

    simplified = result.to_simplified_dict()

    assert simplified["total"] == 2
    assert simplified["start_at"] == 5
    assert [issue["key"] for issue in simplified["issues"]] == ["OPS-1", "OPS-2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/jira/test_schemas.py -v`
Expected: FAIL because the current Jira schema module does not define `from_api_response()`, `JiraSearchResult`, or a Cloud-aware user/resource shape.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/atlassian_cli/products/jira/schemas.py
from typing import Any

from pydantic import Field

from atlassian_cli.models.base import ApiModel
from atlassian_cli.models.common import adf_to_text, coerce_str, first_present, nested_get


class JiraUser(ApiModel):
    account_id: str | None = None
    name: str | None = None
    key: str | None = None
    display_name: str = "Unassigned"
    email: str | None = None
    avatar_url: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraUser":
        data = data or {}
        avatars = data.get("avatarUrls") if isinstance(data.get("avatarUrls"), dict) else {}
        return cls(
            account_id=coerce_str(data.get("accountId")),
            name=coerce_str(first_present(data.get("name"), data.get("username"))),
            key=coerce_str(data.get("key")),
            display_name=str(first_present(data.get("displayName"), "Unassigned")),
            email=coerce_str(first_present(data.get("emailAddress"), data.get("email"))),
            avatar_url=coerce_str(avatars.get("48x48")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "display_name": self.display_name,
            "name": self.name or self.display_name,
            "key": self.key,
            "account_id": self.account_id,
            "email": self.email,
            "avatar_url": self.avatar_url,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


class JiraNamedField(ApiModel):
    name: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraNamedField":
        data = data or {}
        return cls(name=str(data.get("name", "")))

    def to_simplified_dict(self) -> dict[str, Any]:
        return {"name": self.name}


class JiraProject(ApiModel):
    id: str | None = None
    key: str = ""
    name: str = ""
    description: str | None = None
    lead: JiraUser | None = None
    category: str | None = None
    avatar_url: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraProject":
        data = data or {}
        avatars = data.get("avatarUrls") if isinstance(data.get("avatarUrls"), dict) else {}
        category = data.get("projectCategory") if isinstance(data.get("projectCategory"), dict) else {}
        lead = JiraUser.from_api_response(data.get("lead")) if data.get("lead") else None
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            description=coerce_str(data.get("description")),
            lead=lead,
            category=coerce_str(category.get("name")),
            avatar_url=coerce_str(avatars.get("48x48")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "key": self.key, "name": self.name}
        if self.description:
            payload["description"] = self.description
        if self.lead:
            payload["lead"] = self.lead.to_simplified_dict()
        if self.category:
            payload["category"] = self.category
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class JiraIssue(ApiModel):
    id: str | None = None
    key: str = ""
    summary: str = ""
    description: str | None = None
    status: JiraNamedField | None = None
    issue_type: JiraNamedField | None = None
    priority: JiraNamedField | None = None
    assignee: JiraUser | None = None
    reporter: JiraUser | None = None
    labels: list[str] = Field(default_factory=list)
    project: JiraProject | None = None
    created: str | None = None
    updated: str | None = None
    url: str | None = None
    comments: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    parent: dict[str, Any] | None = None
    subtasks: list[dict[str, Any]] = Field(default_factory=list)
    resolution: JiraNamedField | None = None
    duedate: str | None = None
    resolutiondate: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraIssue":
        data = data or {}
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        raw_description = fields.get("description")
        description = adf_to_text(raw_description) if isinstance(raw_description, dict) else coerce_str(raw_description)
        comments = []
        comment_items = nested_get(fields, "comment", "comments")
        if isinstance(comment_items, list):
            comments = [
                {
                    "id": coerce_str(item.get("id")),
                    "body": adf_to_text(item.get("body")) if isinstance(item.get("body"), dict) else coerce_str(item.get("body")),
                    "author": JiraUser.from_api_response(item.get("author")).to_simplified_dict()
                    if item.get("author")
                    else None,
                }
                for item in comment_items
                if isinstance(item, dict)
            ]
        attachments = [
            {
                "id": coerce_str(item.get("id")),
                "filename": coerce_str(item.get("filename")),
                "mime_type": coerce_str(item.get("mimeType")),
            }
            for item in fields.get("attachment", [])
            if isinstance(item, dict)
        ]
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            summary=str(fields.get("summary", "")),
            description=description,
            status=JiraNamedField.from_api_response(fields.get("status")) if fields.get("status") else None,
            issue_type=JiraNamedField.from_api_response(fields.get("issuetype")) if fields.get("issuetype") else None,
            priority=JiraNamedField.from_api_response(fields.get("priority")) if fields.get("priority") else None,
            assignee=JiraUser.from_api_response(fields.get("assignee")) if fields.get("assignee") else None,
            reporter=JiraUser.from_api_response(fields.get("reporter")) if fields.get("reporter") else None,
            labels=[str(label) for label in fields.get("labels", []) if label],
            project=JiraProject.from_api_response(fields.get("project")) if fields.get("project") else None,
            created=coerce_str(fields.get("created")),
            updated=coerce_str(fields.get("updated")),
            url=coerce_str(data.get("self")),
            comments=comments,
            attachments=attachments,
            parent=fields.get("parent") if isinstance(fields.get("parent"), dict) else None,
            subtasks=[item for item in fields.get("subtasks", []) if isinstance(item, dict)],
            resolution=JiraNamedField.from_api_response(fields.get("resolution")) if fields.get("resolution") else None,
            duedate=coerce_str(fields.get("duedate")),
            resolutiondate=coerce_str(fields.get("resolutiondate")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "key": self.key,
            "summary": self.summary,
            "description": self.description,
            "created": self.created,
            "updated": self.updated,
            "url": self.url,
            "labels": self.labels,
            "comments": self.comments,
            "attachments": self.attachments,
            "parent": self.parent,
            "subtasks": self.subtasks,
            "duedate": self.duedate,
            "resolutiondate": self.resolutiondate,
        }
        if self.status:
            payload["status"] = self.status.to_simplified_dict()
        if self.issue_type:
            payload["issue_type"] = self.issue_type.to_simplified_dict()
        if self.priority:
            payload["priority"] = self.priority.to_simplified_dict()
        if self.assignee:
            payload["assignee"] = self.assignee.to_simplified_dict()
        else:
            payload["assignee"] = {"display_name": "Unassigned", "name": "Unassigned"}
        if self.reporter:
            payload["reporter"] = self.reporter.to_simplified_dict()
        if self.project:
            payload["project"] = self.project.to_simplified_dict()
        if self.resolution:
            payload["resolution"] = self.resolution.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, [], {})}


class JiraSearchResult(ApiModel):
    total: int = -1
    start_at: int = 0
    max_results: int = 0
    issues: list[JiraIssue] = Field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraSearchResult":
        data = data or {}
        return cls(
            total=int(data.get("total", -1)),
            start_at=int(data.get("startAt", 0)),
            max_results=int(data.get("maxResults", 0)),
            issues=[
                JiraIssue.from_api_response(item)
                for item in data.get("issues", [])
                if isinstance(item, dict)
            ],
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "start_at": self.start_at,
            "max_results": self.max_results,
            "issues": [issue.to_simplified_dict() for issue in self.issues],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/jira/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/schemas.py tests/products/jira/test_schemas.py
git commit -m "refactor: add jira resource models"
```

## Task 4: Refactor Jira Services And Commands To Use Resource Models

**Files:**
- Modify: `src/atlassian_cli/products/jira/services/issue.py`
- Modify: `src/atlassian_cli/products/jira/services/project.py`
- Modify: `src/atlassian_cli/products/jira/services/user.py`
- Modify: `tests/products/jira/test_issue_service.py`
- Modify: `tests/products/jira/test_project_service.py`
- Create: `tests/products/jira/test_project_command.py`
- Create: `tests/products/jira/test_user_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.jira.services.issue import IssueService
from atlassian_cli.products.jira.services.project import ProjectService
from atlassian_cli.products.jira.services.user import UserService


class FakeIssueProvider:
    def get_issue(self, issue_key: str) -> dict:
        return {
            "id": 1,
            "key": issue_key,
            "fields": {"summary": "Broken deploy", "status": {"name": "Open"}},
        }

    def search_issues(self, jql: str, start: int, limit: int) -> dict:
        return {
            "total": 2,
            "startAt": start,
            "maxResults": limit,
            "issues": [
                {"id": 1, "key": "OPS-1", "fields": {"summary": "Broken deploy", "status": {"name": "Open"}}},
                {"id": 2, "key": "OPS-2", "fields": {"summary": "Fix flaky test", "status": {"name": "Done"}}},
            ],
        }


class FakeProjectProvider:
    def list_projects(self) -> list[dict]:
        return [{"id": 1, "key": "OPS", "name": "Operations"}]


class FakeUserProvider:
    def search_users(self, query: str) -> list[dict]:
        return [{"accountId": "abc-123", "displayName": "Cloud User"}]


def test_issue_service_search_returns_envelope() -> None:
    service = IssueService(provider=FakeIssueProvider())

    result = service.search("project = OPS", start=0, limit=2)

    assert result["total"] == 2
    assert [item["key"] for item in result["issues"]] == ["OPS-1", "OPS-2"]


def test_project_service_list_returns_results_envelope() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.list()

    assert result == {"results": [{"id": "1", "key": "OPS", "name": "Operations"}]}


def test_user_service_search_returns_results_envelope() -> None:
    service = UserService(provider=FakeUserProvider())

    result = service.search("cloud")

    assert result == {
        "results": [
            {
                "display_name": "Cloud User",
                "name": "Cloud User",
                "account_id": "abc-123",
            }
        ]
    }
```

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_project_list_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import project as project_module

    monkeypatch.setattr(
        project_module,
        "build_project_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"list": lambda self: {"results": [{"id": "1", "key": "OPS", "name": "Operations"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "project", "list", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout


def test_jira_user_search_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import user as user_module

    monkeypatch.setattr(
        user_module,
        "build_user_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"search": lambda self, query: {"results": [{"display_name": "Cloud User", "name": "Cloud User"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "user", "search", "--query", "cloud", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/jira/test_issue_service.py tests/products/jira/test_project_service.py tests/products/jira/test_project_command.py tests/products/jira/test_user_command.py -v`
Expected: FAIL because the current services still return thin dictionaries or bare lists and `IssueService.search()` still expects a list rather than a raw search envelope.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/atlassian_cli/products/jira/services/issue.py
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraIssue, JiraSearchResult


class IssueService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(self, issue_key: str) -> dict:
        return JiraIssue.from_api_response(self.provider.get_issue(issue_key)).to_simplified_dict()

    def get_raw(self, issue_key: str) -> dict:
        return self.provider.get_issue(issue_key)

    def search(self, jql: str, start: int, limit: int) -> dict:
        raw = self.provider.search_issues(jql, start, limit)
        return JiraSearchResult.from_api_response(raw).to_simplified_dict()

    def search_raw(self, jql: str, start: int, limit: int) -> dict:
        return self.provider.search_issues(jql, start, limit)

    def create(self, fields: dict) -> dict:
        raw = self.provider.create_issue(fields)
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            return JiraIssue.from_api_response(raw).to_simplified_dict()
        if isinstance(raw, dict) and "key" in raw:
            return {"key": raw["key"]}
        return raw

    def create_raw(self, fields: dict) -> dict:
        return self.provider.create_issue(fields)

    def update(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def update_raw(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def transition(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)

    def transition_raw(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)
```

```python
# src/atlassian_cli/products/jira/services/project.py
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraProject


class ProjectService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def list(self) -> dict:
        projects = [
            JiraProject.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_projects()
        ]
        return {"results": projects}

    def get(self, project_key: str) -> dict:
        return JiraProject.from_api_response(self.provider.get_project(project_key)).to_simplified_dict()

    def list_raw(self) -> list[dict]:
        return self.provider.list_projects()

    def get_raw(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
```

```python
# src/atlassian_cli/products/jira/services/user.py
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraUser


class UserService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(self, username: str) -> dict:
        return JiraUser.from_api_response(self.provider.get_user(username)).to_simplified_dict()

    def get_raw(self, username: str) -> dict:
        return self.provider.get_user(username)

    def search(self, query: str) -> dict:
        users = [
            JiraUser.from_api_response(item).to_simplified_dict()
            for item in self.provider.search_users(query)
        ]
        return {"results": users}

    def search_raw(self, query: str) -> list[dict]:
        return self.provider.search_users(query)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/jira/test_issue_service.py tests/products/jira/test_project_service.py tests/products/jira/test_project_command.py tests/products/jira/test_user_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/services/issue.py src/atlassian_cli/products/jira/services/project.py src/atlassian_cli/products/jira/services/user.py tests/products/jira/test_issue_service.py tests/products/jira/test_project_service.py tests/products/jira/test_project_command.py tests/products/jira/test_user_command.py
git commit -m "refactor: route jira output through resource models"
```

## Task 5: Upgrade Confluence Schemas And Services To Model-First Output

**Files:**
- Modify: `src/atlassian_cli/products/confluence/schemas.py`
- Modify: `src/atlassian_cli/products/confluence/services/page.py`
- Modify: `src/atlassian_cli/products/confluence/services/space.py`
- Modify: `src/atlassian_cli/products/confluence/services/attachment.py`
- Modify: `tests/products/confluence/test_page_service.py`
- Modify: `tests/products/confluence/test_space_service.py`
- Create: `tests/products/confluence/test_schemas.py`
- Create: `tests/products/confluence/test_space_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.confluence.schemas import ConfluenceAttachment, ConfluencePage, ConfluenceSpace


def test_confluence_page_from_api_response_builds_rich_resource() -> None:
    page = ConfluencePage.from_api_response(
        {
            "id": 1234,
            "title": "Runbook",
            "type": "page",
            "status": "current",
            "space": {"id": 7, "key": "OPS", "name": "Operations"},
            "version": {"number": 3, "by": {"displayName": "Alice"}},
            "history": {"createdDate": "2026-04-20T10:00:00.000Z"},
        },
        base_url="https://confluence.example.com",
        is_cloud=False,
    )

    simplified = page.to_simplified_dict()

    assert simplified["space"]["key"] == "OPS"
    assert simplified["version"] == 3
    assert "url" in simplified


def test_confluence_space_from_api_response_keeps_status_and_type() -> None:
    space = ConfluenceSpace.from_api_response(
        {"id": 9, "key": "OPS", "name": "Operations", "type": "global", "status": "current"}
    )

    assert space.to_simplified_dict() == {
        "id": "9",
        "key": "OPS",
        "name": "Operations",
        "type": "global",
        "status": "current",
    }


def test_confluence_attachment_from_api_response_reads_download_metadata() -> None:
    attachment = ConfluenceAttachment.from_api_response(
        {
            "id": 55,
            "title": "deploy.log",
            "_links": {"download": "/download/attachments/55/deploy.log"},
            "extensions": {"mediaType": "text/plain", "fileSize": 42},
            "version": {"number": 2, "by": {"displayName": "Alice"}},
        }
    )

    simplified = attachment.to_simplified_dict()

    assert simplified["download_url"] == "/download/attachments/55/deploy.log"
    assert simplified["file_size"] == 42
    assert simplified["author_display_name"] == "Alice"
```

```python
from atlassian_cli.products.confluence.services.page import PageService
from atlassian_cli.products.confluence.services.space import SpaceService


class FakePageProvider:
    def __init__(self) -> None:
        self.client = type("Client", (), {"url": "https://confluence.example.com"})()

    def get_page(self, page_id: str) -> dict:
        return {
            "id": page_id,
            "title": "Runbook",
            "type": "page",
            "status": "current",
            "space": {"id": 1, "key": "OPS", "name": "Operations"},
            "version": {"number": 7},
        }


class FakeSpaceProvider:
    def list_spaces(self, start: int, limit: int) -> dict:
        return {
            "results": [{"id": 1, "key": "OPS", "name": "Operations", "type": "global", "status": "current"}],
            "start": start,
            "limit": limit,
        }


def test_page_service_get_returns_rich_resource() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get("1234")

    assert result["id"] == "1234"
    assert result["space"]["key"] == "OPS"
    assert result["version"] == 7


def test_space_service_list_returns_results_envelope() -> None:
    service = SpaceService(provider=FakeSpaceProvider())

    result = service.list(start=0, limit=25)

    assert result == {
        "results": [{"id": "1", "key": "OPS", "name": "Operations", "type": "global", "status": "current"}],
        "start_at": 0,
        "max_results": 25,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/confluence/test_schemas.py tests/products/confluence/test_page_service.py tests/products/confluence/test_space_service.py tests/products/confluence/test_space_command.py -v`
Expected: FAIL because the current schema module has no model parsing methods, `SpaceService.list()` expects a bare list instead of a paged envelope, and the normalized page and attachment shapes are still too thin.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/atlassian_cli/products/confluence/schemas.py
from typing import Any

from pydantic import Field

from atlassian_cli.models.base import ApiModel, TimestampMixin
from atlassian_cli.models.common import coerce_str, first_present, nested_get


class ConfluenceUserRef(ApiModel):
    display_name: str = "Unknown"
    email: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceUserRef":
        data = data or {}
        return cls(
            display_name=str(first_present(data.get("displayName"), "Unknown")),
            email=coerce_str(first_present(data.get("email"), data.get("emailAddress"))),
        )


class ConfluenceVersion(ApiModel):
    number: int = 0
    by: ConfluenceUserRef | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceVersion":
        data = data or {}
        return cls(
            number=int(data.get("number", 0)),
            by=ConfluenceUserRef.from_api_response(data.get("by")) if data.get("by") else None,
        )


class ConfluenceSpace(ApiModel):
    id: str | None = None
    key: str = ""
    name: str = ""
    type: str | None = None
    status: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceSpace":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            type=coerce_str(data.get("type")),
            status=coerce_str(data.get("status")),
        )


    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "key": self.key, "name": self.name}
        if self.type:
            payload["type"] = self.type
        if self.status:
            payload["status"] = self.status
        return payload


class ConfluenceAttachment(ApiModel):
    id: str | None = None
    title: str = ""
    media_type: str | None = None
    file_size: int | None = None
    download_url: str | None = None
    version_number: int | None = None
    created: str | None = None
    author_display_name: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluenceAttachment":
        data = data or {}
        version = data.get("version") if isinstance(data.get("version"), dict) else {}
        author = version.get("by") if isinstance(version.get("by"), dict) else {}
        extensions = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
        links = data.get("_links") if isinstance(data.get("_links"), dict) else {}
        return cls(
            id=coerce_str(data.get("id")),
            title=str(first_present(data.get("title"), data.get("fileName"), "")),
            media_type=coerce_str(first_present(data.get("mediaType"), extensions.get("mediaType"))),
            file_size=extensions.get("fileSize"),
            download_url=coerce_str(links.get("download")),
            version_number=int(version["number"]) if version.get("number") is not None else None,
            created=coerce_str(data.get("created")),
            author_display_name=coerce_str(author.get("displayName")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "media_type": self.media_type,
            "file_size": self.file_size,
            "download_url": self.download_url,
            "version_number": self.version_number,
            "created": self.created,
            "author_display_name": self.author_display_name,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


class ConfluencePage(ApiModel, TimestampMixin):
    id: str | None = None
    title: str = ""
    type: str | None = None
    status: str | None = None
    space: ConfluenceSpace | None = None
    version: ConfluenceVersion | None = None
    author: ConfluenceUserRef | None = None
    created: str | None = None
    updated: str | None = None
    url: str | None = None
    content: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "ConfluencePage":
        data = data or {}
        space_data = data.get("space")
        if not space_data and isinstance(data.get("_expandable"), dict):
            space_path = data["_expandable"].get("space")
            if isinstance(space_path, str) and space_path.startswith("/rest/api/space/"):
                key = space_path.split("/rest/api/space/")[1]
                space_data = {"key": key, "name": f"Space {key}"}
        space = ConfluenceSpace.from_api_response(space_data) if space_data is not None else None
        version = ConfluenceVersion.from_api_response(data.get("version")) if data.get("version") else None
        history = data.get("history") if isinstance(data.get("history"), dict) else {}
        base_url = kwargs.get("base_url")
        is_cloud = bool(kwargs.get("is_cloud", False))
        url = None
        if base_url and data.get("id") is not None:
            base_url = str(base_url).rstrip("/")
            if is_cloud:
                space_key = space.key if space and space.key else "unknown"
                url = f"{base_url}/spaces/{space_key}/pages/{data['id']}"
            else:
                url = f"{base_url}/pages/viewpage.action?pageId={data['id']}"
        return cls(
            id=coerce_str(data.get("id")),
            title=str(data.get("title", "")),
            type=coerce_str(data.get("type")),
            status=coerce_str(first_present(data.get("status"), "current")),
            space=space,
            version=version,
            author=ConfluenceUserRef.from_api_response(data.get("author")) if data.get("author") else None,
            created=coerce_str(history.get("createdDate")),
            updated=coerce_str(first_present(nested_get(history, "lastUpdated", "when"), nested_get(data, "version", "when"))),
            url=url,
            content=coerce_str(nested_get(data, "body", "storage", "value")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "url": self.url,
        }
        if self.space:
            payload["space"] = self.space.to_simplified_dict()
        if self.version:
            payload["version"] = self.version.number
        if self.author:
            payload["author"] = self.author.display_name
        return {key: value for key, value in payload.items() if value not in (None, "")}
```

```python
# src/atlassian_cli/products/confluence/services/page.py
from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluencePage


class PageService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def _page_kwargs(self) -> dict:
        client = getattr(self.provider, "client", None)
        return {"base_url": getattr(client, "url", None), "is_cloud": False}

    def get(self, page_id: str) -> dict:
        return ConfluencePage.from_api_response(self.provider.get_page(page_id), **self._page_kwargs()).to_simplified_dict()

    def get_raw(self, page_id: str) -> dict:
        return self.provider.get_page(page_id)

    def create(self, *, space_key: str, title: str, body: str) -> dict:
        raw = self.provider.create_page(space_key=space_key, title=title, body=body)
        return ConfluencePage.from_api_response(raw, **self._page_kwargs()).to_simplified_dict()

    def create_raw(self, *, space_key: str, title: str, body: str) -> dict:
        return self.provider.create_page(space_key=space_key, title=title, body=body)

    def update(self, page_id: str, *, title: str, body: str) -> dict:
        raw = self.provider.update_page(page_id=page_id, title=title, body=body)
        return ConfluencePage.from_api_response(raw, **self._page_kwargs()).to_simplified_dict()

    def update_raw(self, page_id: str, *, title: str, body: str) -> dict:
        return self.provider.update_page(page_id=page_id, title=title, body=body)

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)

    def delete_raw(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
```

```python
# src/atlassian_cli/products/confluence/services/space.py
from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceSpace


class SpaceService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> dict:
        raw = self.provider.list_spaces(start=start, limit=limit)
        spaces = [
            ConfluenceSpace.from_api_response(item).to_simplified_dict()
            for item in raw.get("results", [])
            if isinstance(item, dict)
        ]
        payload = {"results": spaces}
        if raw.get("start") is not None:
            payload["start_at"] = raw["start"]
        if raw.get("limit") is not None:
            payload["max_results"] = raw["limit"]
        return payload

    def get(self, space_key: str) -> dict:
        return ConfluenceSpace.from_api_response(self.provider.get_space(space_key)).to_simplified_dict()

    def list_raw(self, start: int, limit: int) -> dict:
        return self.provider.list_spaces(start=start, limit=limit)

    def get_raw(self, space_key: str) -> dict:
        return self.provider.get_space(space_key)
```

```python
# src/atlassian_cli/products/confluence/services/attachment.py
from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceAttachment


class AttachmentService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> dict:
        raw = self.provider.list_attachments(page_id)
        attachments = [
            ConfluenceAttachment.from_api_response(item).to_simplified_dict()
            for item in raw.get("results", [])
            if isinstance(item, dict)
        ]
        payload = {"results": attachments}
        if raw.get("start") is not None:
            payload["start_at"] = raw["start"]
        if raw.get("limit") is not None:
            payload["max_results"] = raw["limit"]
        return payload

    def list_raw(self, page_id: str) -> dict:
        return self.provider.list_attachments(page_id)

    def upload(self, page_id: str, file_path: str) -> dict:
        return ConfluenceAttachment.from_api_response(
            self.provider.upload_attachment(page_id, file_path)
        ).to_simplified_dict()

    def upload_raw(self, page_id: str, file_path: str) -> dict:
        return self.provider.upload_attachment(page_id, file_path)

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_raw(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/confluence/test_schemas.py tests/products/confluence/test_page_service.py tests/products/confluence/test_space_service.py tests/products/confluence/test_space_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/confluence/schemas.py src/atlassian_cli/products/confluence/services/page.py src/atlassian_cli/products/confluence/services/space.py src/atlassian_cli/products/confluence/services/attachment.py tests/products/confluence/test_schemas.py tests/products/confluence/test_page_service.py tests/products/confluence/test_space_service.py tests/products/confluence/test_space_command.py
git commit -m "refactor: route confluence output through resource models"
```

## Task 6: Upgrade Bitbucket Schemas And Fix Pull Request Merge Semantics

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/schemas.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/project.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/repo.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/branch.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/pr.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Modify: `tests/products/bitbucket/test_pr_service.py`
- Modify: `tests/products/bitbucket/test_repo_service.py`
- Modify: `tests/products/bitbucket/test_provider.py`
- Create: `tests/products/bitbucket/test_schemas.py`
- Create: `tests/products/bitbucket/test_pr_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.bitbucket.providers.server import BitbucketServerProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequest
from atlassian_cli.products.bitbucket.services.pr import PullRequestService
from atlassian_cli.products.bitbucket.services.repo import RepoService


class FakePullRequestProvider:
    def __init__(self) -> None:
        self.merge_calls = []

    def list_pull_requests(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return [
            {
                "id": 42,
                "title": "Ship output cleanup",
                "state": "OPEN",
                "version": 7,
                "fromRef": {"displayId": "feature/output"},
                "toRef": {"displayId": "main"},
            }
        ]

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.list_pull_requests(project_key, repo_slug, "OPEN")[0]

    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        merge_message: str,
        pr_version: int | None,
    ) -> dict:
        self.merge_calls.append((project_key, repo_slug, pr_id, merge_message, pr_version))
        return {
            "id": pr_id,
            "title": "Ship output cleanup",
            "state": "MERGED",
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
        }


def test_bitbucket_pr_schema_handles_missing_author_and_reviewers() -> None:
    pr = BitbucketPullRequest.from_api_response(
        {
            "id": 42,
            "title": "Ship output cleanup",
            "state": "OPEN",
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
        }
    )

    simplified = pr.to_simplified_dict()

    assert simplified["from_ref"]["display_id"] == "feature/output"
    assert "author" not in simplified


def test_pull_request_service_merge_prefetches_title_and_version() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.merge("OPS", "infra", 42)

    assert result["state"] == "MERGED"
    assert provider.merge_calls == [
        ("OPS", "infra", 42, "Merge pull request #42: Ship output cleanup", 7)
    ]


class FakeRepoProvider:
    def list_repos(self, project_key: str | None, start: int, limit: int) -> list[dict]:
        return [
            {
                "slug": "infra",
                "name": "Infra",
                "state": "AVAILABLE",
                "project": {"key": "OPS", "name": "Operations"},
            }
        ]


def test_repo_service_list_returns_results_envelope() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.list("OPS", start=0, limit=25)

    assert result == {
        "results": [
            {
                "slug": "infra",
                "name": "Infra",
                "state": "AVAILABLE",
                "project": {"key": "OPS", "name": "Operations"},
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }


def test_bitbucket_provider_merge_pull_request_forwards_message_and_version() -> None:
    calls = {}

    class FakeClient:
        def merge_pull_request(self, project_key, repo_slug, pr_id, merge_message, pr_version=None):
            calls["args"] = (project_key, repo_slug, pr_id, merge_message, pr_version)
            return {"id": pr_id, "state": "MERGED"}

    provider = BitbucketServerProvider.__new__(BitbucketServerProvider)
    provider.client = FakeClient()

    result = provider.merge_pull_request(
        "OPS",
        "infra",
        42,
        merge_message="Merge pull request #42: Ship output cleanup",
        pr_version=7,
    )

    assert result["state"] == "MERGED"
    assert calls["args"] == (
        "OPS",
        "infra",
        42,
        "Merge pull request #42: Ship output cleanup",
        7,
    )
```

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_bitbucket_pr_list_outputs_results_envelope(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state: {
                    "results": [{"id": 42, "title": "Ship output cleanup", "state": "OPEN"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "list", "OPS", "infra", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"results"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/bitbucket/test_schemas.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_provider.py -v`
Expected: FAIL because the current pull request schema raises validation errors on missing nested fields, list services still return bare lists, and the merge path still calls the SDK without a merge message or PR version.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/atlassian_cli/products/bitbucket/schemas.py
from typing import Any

from pydantic import Field

from atlassian_cli.models.base import ApiModel
from atlassian_cli.models.common import coerce_str, first_present, nested_get


class BitbucketUserRef(ApiModel):
    display_name: str | None = None
    name: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketUserRef":
        data = data or {}
        return cls(
            display_name=coerce_str(first_present(data.get("displayName"), data.get("name"))),
            name=coerce_str(data.get("name")),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"display_name": self.display_name, "name": self.name}
        return {key: value for key, value in payload.items() if value not in (None, "")}


class BitbucketRef(ApiModel):
    id: str | None = None
    display_id: str | None = None
    latest_commit: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketRef":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            display_id=coerce_str(first_present(data.get("displayId"), data.get("display_id"))),
            latest_commit=coerce_str(data.get("latestCommit")),
        )


class BitbucketReviewer(ApiModel):
    user: BitbucketUserRef | None = None
    approved: bool = False

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketReviewer":
        data = data or {}
        user_data = data.get("user") if isinstance(data.get("user"), dict) else {}
        return cls(
            user=BitbucketUserRef.from_api_response(user_data) if user_data else None,
            approved=bool(data.get("approved", False)),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {"approved": self.approved}
        if self.user:
            payload.update(self.user.to_simplified_dict())
        return payload


class BitbucketProject(ApiModel):
    id: str | None = None
    key: str = ""
    name: str = ""
    description: str | None = None
    public: bool | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketProject":
        data = data or {}
        return cls(
            id=coerce_str(data.get("id")),
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            description=coerce_str(data.get("description")),
            public=data.get("public"),
        )


class BitbucketRepo(ApiModel):
    slug: str = ""
    name: str = ""
    state: str | None = None
    project: BitbucketProject | None = None
    public: bool | None = None
    archived: bool | None = None
    forkable: bool | None = None
    default_branch: BitbucketRef | None = None
    links: dict[str, Any] | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketRepo":
        data = data or {}
        return cls(
            slug=str(data.get("slug", "")),
            name=str(data.get("name", "")),
            state=coerce_str(data.get("state")),
            project=BitbucketProject.from_api_response(data.get("project")) if data.get("project") else None,
            public=data.get("public"),
            archived=data.get("archived"),
            forkable=data.get("forkable"),
            default_branch=BitbucketRef.from_api_response(data.get("defaultBranch"))
            if isinstance(data.get("defaultBranch"), dict)
            else None,
            links=data.get("links") if isinstance(data.get("links"), dict) else None,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "slug": self.slug,
            "name": self.name,
            "state": self.state,
            "public": self.public,
            "archived": self.archived,
            "forkable": self.forkable,
            "links": self.links,
        }
        if self.project:
            payload["project"] = self.project.to_simplified_dict()
        if self.default_branch:
            payload["default_branch"] = self.default_branch.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


class BitbucketPullRequest(ApiModel):
    id: int
    title: str
    description: str | None = None
    state: str | None = None
    open: bool | None = None
    closed: bool | None = None
    author: BitbucketUserRef | None = None
    reviewers: list[BitbucketReviewer] = Field(default_factory=list)
    participants: list[dict[str, Any]] = Field(default_factory=list)
    from_ref: BitbucketRef | None = None
    to_ref: BitbucketRef | None = None
    created_date: str | None = None
    updated_date: str | None = None
    links: dict[str, Any] | None = None
    version: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "BitbucketPullRequest":
        data = data or {}
        author_user = nested_get(data, "author", "user")
        return cls(
            id=int(data.get("id", 0)),
            title=str(data.get("title", "")),
            description=coerce_str(data.get("description")),
            state=coerce_str(data.get("state")),
            open=data.get("open"),
            closed=data.get("closed"),
            author=BitbucketUserRef.from_api_response(author_user) if isinstance(author_user, dict) else None,
            reviewers=[
                BitbucketReviewer.from_api_response(item)
                for item in data.get("reviewers", [])
                if isinstance(item, dict)
            ],
            participants=[item for item in data.get("participants", []) if isinstance(item, dict)],
            from_ref=BitbucketRef.from_api_response(data.get("fromRef")) if isinstance(data.get("fromRef"), dict) else None,
            to_ref=BitbucketRef.from_api_response(data.get("toRef")) if isinstance(data.get("toRef"), dict) else None,
            created_date=coerce_str(first_present(data.get("createdDate"), data.get("created_date"))),
            updated_date=coerce_str(first_present(data.get("updatedDate"), data.get("updated_date"))),
            links=data.get("links") if isinstance(data.get("links"), dict) else None,
            version=data.get("version"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state,
            "open": self.open,
            "closed": self.closed,
            "participants": self.participants,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
            "links": self.links,
        }
        if self.author:
            payload["author"] = self.author.to_simplified_dict()
        if self.reviewers:
            payload["reviewers"] = [item.to_simplified_dict() for item in self.reviewers]
        if self.from_ref:
            payload["from_ref"] = self.from_ref.to_simplified_dict()
        if self.to_ref:
            payload["to_ref"] = self.to_ref.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}
```

```python
# src/atlassian_cli/products/bitbucket/services/pr.py
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequest


class PullRequestService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, state: str) -> dict:
        prs = [
            BitbucketPullRequest.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_pull_requests(project_key, repo_slug, state)
        ]
        return {"results": prs}

    def list_raw(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return self.provider.list_pull_requests(project_key, repo_slug, state)

    def get(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return BitbucketPullRequest.from_api_response(
            self.provider.get_pull_request(project_key, repo_slug, pr_id)
        ).to_simplified_dict()

    def get_raw(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.get_pull_request(project_key, repo_slug, pr_id)

    def create(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return BitbucketPullRequest.from_api_response(
            self.provider.create_pull_request(project_key, repo_slug, payload)
        ).to_simplified_dict()

    def create_raw(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.provider.create_pull_request(project_key, repo_slug, payload)

    def merge(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        current = self.provider.get_pull_request(project_key, repo_slug, pr_id)
        title = current.get("title") or f"Pull request {pr_id}"
        version = current.get("version")
        raw = self.provider.merge_pull_request(
            project_key,
            repo_slug,
            pr_id,
            merge_message=f"Merge pull request #{pr_id}: {title}",
            pr_version=version,
        )
        return BitbucketPullRequest.from_api_response(raw).to_simplified_dict()

    def merge_raw(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        current = self.provider.get_pull_request(project_key, repo_slug, pr_id)
        title = current.get("title") or f"Pull request {pr_id}"
        version = current.get("version")
        return self.provider.merge_pull_request(
            project_key,
            repo_slug,
            pr_id,
            merge_message=f"Merge pull request #{pr_id}: {title}",
            pr_version=version,
        )
```

```python
# src/atlassian_cli/products/bitbucket/services/project.py
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketProject


class ProjectService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> dict:
        projects = [
            BitbucketProject.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_projects(start=start, limit=limit)
        ]
        return {"results": projects, "start_at": start, "max_results": limit}

    def get(self, project_key: str) -> dict:
        return BitbucketProject.from_api_response(self.provider.get_project(project_key)).to_simplified_dict()

    def list_raw(self, start: int, limit: int) -> list[dict]:
        return self.provider.list_projects(start=start, limit=limit)

    def get_raw(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
```

```python
# src/atlassian_cli/products/bitbucket/services/branch.py
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketRef


class BranchService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, filter_text: str | None) -> dict:
        branches = [
            BitbucketRef.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_branches(project_key, repo_slug, filter_text)
        ]
        return {"results": branches}

    def list_raw(self, project_key: str, repo_slug: str, filter_text: str | None) -> list[dict]:
        return self.provider.list_branches(project_key, repo_slug, filter_text)
```

```python
# src/atlassian_cli/products/bitbucket/providers/server.py
def merge_pull_request(
    self,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    *,
    merge_message: str,
    pr_version: int | None,
) -> dict:
    return self.client.merge_pull_request(
        project_key,
        repo_slug,
        pr_id,
        merge_message,
        pr_version=pr_version,
    )
```

```python
# src/atlassian_cli/products/bitbucket/services/repo.py
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketRepo


class RepoService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, project_key: str | None, start: int, limit: int) -> dict:
        repos = [
            BitbucketRepo.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_repos(project_key=project_key, start=start, limit=limit)
        ]
        return {"results": repos, "start_at": start, "max_results": limit}

    def get(self, project_key: str, repo_slug: str) -> dict:
        return BitbucketRepo.from_api_response(self.provider.get_repo(project_key, repo_slug)).to_simplified_dict()

    def list_raw(self, project_key: str | None, start: int, limit: int) -> list[dict]:
        return self.provider.list_repos(project_key=project_key, start=start, limit=limit)

    def get_raw(self, project_key: str, repo_slug: str) -> dict:
        return self.provider.get_repo(project_key, repo_slug)

    def create(self, project_key: str, name: str, scm_id: str) -> dict:
        return BitbucketRepo.from_api_response(
            self.provider.create_repo(project_key=project_key, name=name, scm_id=scm_id)
        ).to_simplified_dict()

    def create_raw(self, project_key: str, name: str, scm_id: str) -> dict:
        return self.provider.create_repo(project_key=project_key, name=name, scm_id=scm_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/products/bitbucket/test_schemas.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/bitbucket/schemas.py src/atlassian_cli/products/bitbucket/services/project.py src/atlassian_cli/products/bitbucket/services/repo.py src/atlassian_cli/products/bitbucket/services/branch.py src/atlassian_cli/products/bitbucket/services/pr.py src/atlassian_cli/products/bitbucket/providers/server.py tests/products/bitbucket/test_schemas.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_repo_service.py tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_provider.py
git commit -m "refactor: route bitbucket output through resource models"
```

## Task 7: Update Documentation And Smoke Coverage For The New Contracts

**Files:**
- Modify: `README.md`
- Create: `tests/test_readme.py`
- Modify: `tests/integration/test_smoke.py`

- [ ] **Step 1: Write the failing tests**

```python
import os

import pytest


@pytest.mark.skipif(not os.getenv("ATLASSIAN_SMOKE"), reason="smoke env not configured")
def test_smoke_suite_has_required_env() -> None:
    assert os.getenv("ATLASSIAN_URL")
    assert os.getenv("ATLASSIAN_PRODUCT")
    assert os.getenv("ATLASSIAN_OUTPUT", "json") in {"json", "yaml", "raw-json", "raw-yaml"}
```

```python
from pathlib import Path


def test_readme_mentions_model_first_normalized_output() -> None:
    readme = Path("README.md").read_text()

    assert "resource-shaped payloads" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_readme.py tests/integration/test_smoke.py -v`
Expected: FAIL because the README does not yet describe resource-shaped normalized output and the smoke suite does not yet state the explicit output mode expectation.

- [ ] **Step 3: Write the minimal implementation**

```markdown
<!-- README.md -->
## Output Modes

`json` and `yaml` return CLI-owned resource-shaped payloads by default.

- Single-resource commands return a resource object.
- Collection commands return explicit envelopes such as `results` or `issues`.
- Use `--output raw-json` or `--output raw-yaml` to inspect the raw provider payload.

Examples:

- `atlassian jira issue get OPS-1 --output json`
- `atlassian jira issue search --jql 'project = OPS' --output json`
- `atlassian confluence space list --output json`
- `atlassian bitbucket pr list OPS infra --output json`
```

```python
# tests/test_readme.py
from pathlib import Path


def test_readme_mentions_model_first_normalized_output() -> None:
    readme = Path("README.md").read_text()

    assert "resource-shaped payloads" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
```

```python
# tests/integration/test_smoke.py
import os

import pytest


@pytest.mark.skipif(not os.getenv("ATLASSIAN_SMOKE"), reason="smoke env not configured")
def test_smoke_suite_has_required_env() -> None:
    assert os.getenv("ATLASSIAN_URL")
    assert os.getenv("ATLASSIAN_PRODUCT")
    assert os.getenv("ATLASSIAN_OUTPUT", "json") in {"json", "yaml", "raw-json", "raw-yaml"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/test_readme.py tests/integration/test_smoke.py -v`
Expected: PASS or SKIP depending on environment

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py tests/integration/test_smoke.py
git commit -m "docs: describe model-first output contracts"
```

## Final Verification

- [ ] Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest tests/models/test_base.py tests/test_readme.py tests/output/test_renderers.py tests/products/jira tests/products/confluence tests/products/bitbucket tests/products/test_factory.py tests/products/test_header_providers.py tests/integration/test_smoke.py -v`
Expected: PASS with smoke either PASS or SKIP depending on environment

- [ ] Run: `/Users/admin/atlassian-cli/.venv/bin/python -m pytest -q`
Expected: PASS
