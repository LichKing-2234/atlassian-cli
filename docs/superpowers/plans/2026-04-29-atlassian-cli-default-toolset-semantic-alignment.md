# Atlassian CLI Default Toolset Semantic Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the CLI's default Jira and Confluence command behavior with `mcp-atlassian` `TOOLSETS=default` at the level of input semantics, execution semantics, and normalized output, while hardening the live e2e suite against real-instance variability.

**Architecture:** Keep the existing `command -> service -> provider -> schema/model` flow. Put MCP-like parameter semantics in command modules, instance-aware validation and orchestration in services, raw API interaction in providers, and richer default output contracts in product schemas plus markdown rendering. Add test-only discovery helpers under `tests/e2e/support/` so live tests adapt without contaminating production code.

**Tech Stack:** Python 3.12+, Typer, `atlassian-python-api`, Pydantic models, Rich/markdown output helpers, pytest

---

## Planned File Structure

### Modify

- `README.md`
- `CONTRIBUTING.md`
- `src/atlassian_cli/output/markdown.py`
- `src/atlassian_cli/products/jira/commands/issue.py`
- `src/atlassian_cli/products/jira/providers/base.py`
- `src/atlassian_cli/products/jira/providers/server.py`
- `src/atlassian_cli/products/jira/services/issue.py`
- `src/atlassian_cli/products/jira/schemas.py`
- `src/atlassian_cli/products/confluence/commands/page.py`
- `src/atlassian_cli/products/confluence/providers/base.py`
- `src/atlassian_cli/products/confluence/providers/server.py`
- `src/atlassian_cli/products/confluence/services/page.py`
- `src/atlassian_cli/products/confluence/schemas.py`
- `tests/output/test_markdown.py`
- `tests/products/jira/test_issue_command.py`
- `tests/products/jira/test_issue_service.py`
- `tests/products/confluence/test_page_command.py`
- `tests/products/confluence/test_page_service.py`
- `tests/e2e/support/__init__.py`
- `tests/e2e/support/env.py`
- `tests/e2e/test_jira_live.py`
- `tests/e2e/test_confluence_live.py`
- `tests/e2e/test_bitbucket_live.py`
- `tests/e2e/test_support.py`
- `tests/test_readme.py`

### Create

- `tests/e2e/support/discovery.py`

### Responsibilities

- `src/atlassian_cli/products/jira/commands/issue.py` owns the MCP-like CLI surface for Jira issue get/search/create/update/batch-create/changelog-batch.
- `src/atlassian_cli/products/jira/services/issue.py` owns Jira issue read/write orchestration, create metadata validation, and normalized write envelopes.
- `src/atlassian_cli/products/jira/providers/base.py` and `server.py` own Jira SDK parameter expansion and metadata access.
- `src/atlassian_cli/products/jira/schemas.py` owns richer normalized Jira issue and write-result shapes.
- Existing Jira field, comment, and transition modules stay in place; their contract stability is protected by targeted existing tests plus full-suite verification after the shared Jira semantic changes land.
- `src/atlassian_cli/products/confluence/commands/page.py` owns the MCP-like CLI surface for Confluence search/get/history/create/update.
- `src/atlassian_cli/products/confluence/services/page.py` owns Confluence search-mode selection, page content envelope shaping, and normalized write envelopes.
- `src/atlassian_cli/products/confluence/providers/base.py` and `server.py` own expanded page read/search/write capabilities against `atlassian-python-api`.
- `src/atlassian_cli/products/confluence/schemas.py` owns richer normalized page resources and any page-content envelope helpers.
- `src/atlassian_cli/output/markdown.py` owns markdown rendering for `message + resource` and `metadata/content` envelopes.
- Existing Confluence comment modules stay in place; their current command/service split is retained and validated through the final full-suite run once page envelope rendering changes are complete.
- `tests/e2e/support/discovery.py` owns test-only live-instance probing and minimal payload construction for Jira, Confluence, and Bitbucket.

## Common Commands

- Install deps: `.venv/bin/pip install -e '.[dev]'`
- Jira focused tests: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/jira/test_issue_service.py tests/products/jira/test_issue_command.py -v`
- Confluence focused tests: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py tests/output/test_markdown.py -v`
- Live support focused tests: `PYTHONPATH=src .venv/bin/python -m pytest tests/e2e/test_support.py -v`
- Full verification: `PYTHONPATH=src .venv/bin/ruff format --check . && PYTHONPATH=src .venv/bin/python -m pytest -q && PYTHONPATH=src .venv/bin/ruff check README.md pyproject.toml src tests docs`

### Task 1: Expand Jira Issue Semantics In Provider, Service, And Schema Layers

**Files:**
- Modify: `src/atlassian_cli/products/jira/providers/base.py`
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Modify: `src/atlassian_cli/products/jira/services/issue.py`
- Modify: `src/atlassian_cli/products/jira/schemas.py`
- Modify: `tests/products/jira/test_issue_service.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

from atlassian_cli.products.jira.services.issue import IssueService


class FakeSemanticIssueProvider:
    def __init__(self) -> None:
        self.get_calls: list[dict] = []
        self.search_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []

    def get_issue(
        self,
        issue_key: str,
        *,
        fields=None,
        expand=None,
        comment_limit: int = 10,
        properties=None,
        update_history: bool = True,
    ) -> dict:
        self.get_calls.append(
            {
                "issue_key": issue_key,
                "fields": fields,
                "expand": expand,
                "comment_limit": comment_limit,
                "properties": properties,
                "update_history": update_history,
            }
        )
        return {
            "id": "10000",
            "key": issue_key,
            "fields": {
                "summary": "Example issue summary",
                "description": "Investigate rollout health",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Example Author"},
                "updated": "2026-04-29T09:00:00.000+0000",
            },
        }

    def search_issues(
        self,
        jql: str,
        *,
        fields=None,
        expand=None,
        start_at: int = 0,
        limit: int = 10,
        projects_filter=None,
    ) -> dict:
        self.search_calls.append(
            {
                "jql": jql,
                "fields": fields,
                "expand": expand,
                "start_at": start_at,
                "limit": limit,
                "projects_filter": projects_filter,
            }
        )
        return {
            "startAt": start_at,
            "maxResults": limit,
            "total": 1,
            "issues": [
                {
                    "id": "10000",
                    "key": "DEMO-1",
                    "fields": {
                        "summary": "Example issue summary",
                        "status": {"name": "Open"},
                    },
                }
            ],
        }

    def get_create_meta(self, project_key: str, issue_type: str) -> dict:
        assert project_key == "DEMO"
        assert issue_type == "Task"
        return {
            "required": ["customfield_10001"],
            "allowed_values": {"customfield_10001": [{"id": "11", "value": "Linux"}]},
        }

    def create_issue(self, fields: dict) -> dict:
        self.create_calls.append(fields)
        return {
            "id": "10001",
            "key": "DEMO-2",
            "fields": {
                "summary": fields["summary"],
                "description": fields.get("description"),
                "status": {"name": "Open"},
            },
        }

    def update_issue(self, issue_key: str, fields: dict) -> dict:
        self.update_calls.append({"issue_key": issue_key, "fields": fields})
        return {
            "id": "10000",
            "key": issue_key,
            "fields": {
                "summary": "Updated summary",
                "description": "Updated description",
                "status": {"name": "In Progress"},
            },
            "attachment_results": [{"filename": "release.txt", "status": "attached"}],
        }


def test_issue_service_get_passes_mcp_style_read_options() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.get(
        "DEMO-1",
        fields=["summary", "status"],
        expand="renderedFields",
        comment_limit=5,
        properties=["triage", "ops"],
        update_history=False,
    )

    assert result["key"] == "DEMO-1"
    assert provider.get_calls == [
        {
            "issue_key": "DEMO-1",
            "fields": ["summary", "status"],
            "expand": "renderedFields",
            "comment_limit": 5,
            "properties": ["triage", "ops"],
            "update_history": False,
        }
    ]


def test_issue_service_search_returns_mcp_style_envelope() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.search(
        "project = DEMO",
        fields=["summary"],
        expand="changelog",
        start_at=3,
        limit=7,
        projects_filter=["DEMO", "OPS"],
    )

    assert result["start_at"] == 3
    assert result["max_results"] == 7
    assert result["issues"][0]["key"] == "DEMO-1"
    assert provider.search_calls[0]["projects_filter"] == ["DEMO", "OPS"]


def test_issue_service_create_returns_message_and_issue_resource() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.create(
        project_key="DEMO",
        summary="Example issue summary",
        issue_type="Task",
        assignee="example-user",
        description="Investigate rollout health",
        components=["API"],
        additional_fields={"customfield_10001": {"id": "11"}},
    )

    assert result["message"] == "Issue created successfully"
    assert result["issue"]["key"] == "DEMO-2"
    assert provider.create_calls[0]["customfield_10001"] == {"id": "11"}


def test_issue_service_create_raises_for_missing_required_metadata_field() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    try:
        service.create(
            project_key="DEMO",
            summary="Example issue summary",
            issue_type="Task",
            assignee=None,
            description=None,
            components=None,
            additional_fields={},
        )
    except ValueError as exc:
        assert "customfield_10001" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_issue_service_update_returns_message_issue_and_attachment_results() -> None:
    provider = FakeSemanticIssueProvider()
    service = IssueService(provider=provider)

    result = service.update(
        "DEMO-1",
        fields={"summary": "Updated summary", "description": "Updated description"},
        additional_fields={"labels": ["ops"]},
        components=["API"],
        attachments=["release.txt"],
    )

    assert result["message"] == "Issue updated successfully"
    assert result["issue"]["key"] == "DEMO-1"
    assert result["issue"]["attachment_results"] == [{"filename": "release.txt", "status": "attached"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/jira/test_issue_service.py -v`
Expected: FAIL with `TypeError` or missing-method errors because `IssueService` and `JiraProvider` do not yet support MCP-style keyword arguments and write envelopes.

- [ ] **Step 3: Write minimal implementation**

```python
# src/atlassian_cli/products/jira/providers/base.py
class JiraProvider(Protocol):
    def get_issue(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        pass
    def search_issues(
        self,
        jql: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        start_at: int = 0,
        limit: int = 10,
        projects_filter: list[str] | None = None,
    ) -> dict:
        pass
    def get_create_meta(self, project_key: str, issue_type: str) -> dict:
        pass
```

```python
# src/atlassian_cli/products/jira/providers/server.py
def get_issue(
    self,
    issue_key: str,
    *,
    fields: str | list[str] | None = None,
    expand: str | None = None,
    comment_limit: int = 10,
    properties: list[str] | None = None,
    update_history: bool = True,
) -> dict:
    return self.client.issue(
        issue_key,
        fields=fields,
        expand=expand,
        properties=properties,
        update_history=update_history,
    )

def search_issues(
    self,
    jql: str,
    *,
    fields: str | list[str] | None = None,
    expand: str | None = None,
    start_at: int = 0,
    limit: int = 10,
    projects_filter: list[str] | None = None,
) -> dict:
    scoped_jql = jql
    if projects_filter:
        project_clause = ", ".join(projects_filter)
        scoped_jql = f"project in ({project_clause}) AND ({jql})"
    return self.client.jql(scoped_jql, fields=fields, expand=expand, start=start_at, limit=limit)

def get_create_meta(self, project_key: str, issue_type: str) -> dict:
    meta = self.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
    issue_types = meta.get("projects", [{}])[0].get("issuetypes", [])
    selected = next((item for item in issue_types if item.get("name") == issue_type), None)
    if selected is None:
        return {"required": [], "allowed_values": {}}
    fields = selected.get("fields", {})
    return {
        "required": [field_id for field_id, info in fields.items() if info.get("required")],
        "allowed_values": {
            field_id: info.get("allowedValues", [])
            for field_id, info in fields.items()
            if info.get("allowedValues")
        },
    }
```

```python
# src/atlassian_cli/products/jira/services/issue.py
def get(
    self,
    issue_key: str,
    *,
    fields: str | list[str] | None = None,
    expand: str | None = None,
    comment_limit: int = 10,
    properties: list[str] | None = None,
    update_history: bool = True,
) -> dict:
    raw = self.provider.get_issue(
        issue_key,
        fields=fields,
        expand=expand,
        comment_limit=comment_limit,
        properties=properties,
        update_history=update_history,
    )
    return JiraIssue.from_api_response(raw).to_simplified_dict()

def search(
    self,
    jql: str,
    *,
    fields: str | list[str] | None = None,
    expand: str | None = None,
    start_at: int = 0,
    limit: int = 10,
    projects_filter: list[str] | None = None,
) -> dict:
    raw = self.provider.search_issues(
        jql,
        fields=fields,
        expand=expand,
        start_at=start_at,
        limit=limit,
        projects_filter=projects_filter,
    )
    return JiraSearchResult.from_api_response(raw).to_simplified_dict()

def create(
    self,
    *,
    project_key: str,
    summary: str,
    issue_type: str,
    assignee: str | None,
    description: str | None,
    components: list[str] | None,
    additional_fields: dict,
) -> dict:
    meta = self.provider.get_create_meta(project_key, issue_type)
    missing = [field for field in meta.get("required", []) if field not in additional_fields]
    if missing:
        raise ValueError(f"missing required Jira fields: {', '.join(sorted(missing))}")
    payload = {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    if assignee:
        payload["assignee"] = {"name": assignee}
    if description:
        payload["description"] = description
    if components:
        payload["components"] = [{"name": name} for name in components]
    payload.update(additional_fields)
    raw = self.provider.create_issue(payload)
    return {
        "message": "Issue created successfully",
        "issue": JiraIssue.from_api_response(raw).to_simplified_dict(),
    }

def update(
    self,
    issue_key: str,
    *,
    fields: dict,
    additional_fields: dict,
    components: list[str] | None,
    attachments: list[str] | None,
) -> dict:
    payload = {**fields, **additional_fields}
    if components:
        payload["components"] = [{"name": name} for name in components]
    if attachments:
        payload["attachments"] = attachments
    raw = self.provider.update_issue(issue_key, payload)
    issue = JiraIssue.from_api_response(raw).to_simplified_dict()
    if raw.get("attachment_results"):
        issue["attachment_results"] = raw["attachment_results"]
    return {"message": "Issue updated successfully", "issue": issue}
```

```python
# src/atlassian_cli/products/jira/schemas.py
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
    if self.reporter:
        payload["reporter"] = self.reporter.to_simplified_dict()
    if self.project:
        payload["project"] = self.project.to_simplified_dict()
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/jira/test_issue_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/providers/base.py \
  src/atlassian_cli/products/jira/providers/server.py \
  src/atlassian_cli/products/jira/services/issue.py \
  src/atlassian_cli/products/jira/schemas.py \
  tests/products/jira/test_issue_service.py
git commit -m "feat: align jira issue service semantics"
```

### Task 2: Rework Jira Issue Commands Around MCP-Like CLI Inputs

**Files:**
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `tests/products/jira/test_issue_command.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_issue_get_passes_fields_expand_and_comment_limit(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def get(self, issue_key, **kwargs):
            captured["issue_key"] = issue_key
            captured["kwargs"] = kwargs
            return {"key": issue_key, "summary": "Example issue summary"}

    monkeypatch.setattr(issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "get",
            "DEMO-1",
            "--fields",
            "summary,status",
            "--expand",
            "renderedFields",
            "--comment-limit",
            "5",
            "--properties",
            "triage,ops",
            "--update-history",
            "false",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["kwargs"] == {
        "fields": ["summary", "status"],
        "expand": "renderedFields",
        "comment_limit": 5,
        "properties": ["triage", "ops"],
        "update_history": False,
    }


def test_jira_issue_create_accepts_additional_fields(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def create(self, **kwargs):
            captured.update(kwargs)
            return {"message": "Issue created successfully", "issue": {"key": "DEMO-2"}}

    monkeypatch.setattr(issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "create",
            "--project-key",
            "DEMO",
            "--issue-type",
            "Task",
            "--summary",
            "Example issue summary",
            "--assignee",
            "example-user",
            "--description",
            "Investigate rollout health",
            "--components",
            "API,CLI",
            "--additional-fields",
            '{"customfield_10001":{"id":"11"}}',
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["components"] == ["API", "CLI"]
    assert captured["additional_fields"] == {"customfield_10001": {"id": "11"}}


def test_jira_issue_update_accepts_fields_attachments_and_additional_fields(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def update(self, issue_key, **kwargs):
            captured["issue_key"] = issue_key
            captured["kwargs"] = kwargs
            return {"message": "Issue updated successfully", "issue": {"key": issue_key}}

    monkeypatch.setattr(issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "update",
            "DEMO-1",
            "--fields",
            '{"summary":"Updated summary"}',
            "--additional-fields",
            '{"labels":["ops"]}',
            "--components",
            "API",
            "--attachments",
            '["release.txt"]',
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["kwargs"]["fields"] == {"summary": "Updated summary"}
    assert captured["kwargs"]["attachments"] == ["release.txt"]


def test_jira_issue_batch_create_accepts_inline_json_and_validate_only(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def batch_create(self, issues, *, validate_only: bool):
            captured["issues"] = issues
            captured["validate_only"] = validate_only
            return {"message": "Issues validated successfully", "issues": [{"key": "DEMO-1"}]}

    monkeypatch.setattr(issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "batch-create",
            "--issues",
            '[{"project_key":"DEMO","summary":"Example issue summary","issue_type":"Task"}]',
            "--validate-only",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["validate_only"] is True
    assert captured["issues"][0]["project_key"] == "DEMO"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/jira/test_issue_command.py -v`
Expected: FAIL because the command layer still exposes the old parameter model and file-based batch-create input.

- [ ] **Step 3: Write minimal implementation**

```python
# src/atlassian_cli/products/jira/commands/issue.py
def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    values = [item.strip() for item in value.split(",") if item.strip()]
    return values or None

def _parse_json_option(value: str | None, *, option_name: str) -> dict:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid JSON for {option_name}: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter(f"{option_name} must be a JSON object")
    return parsed

def _parse_issue_batch(value: str) -> list[dict]:
    raw = Path(value[1:]).read_text() if value.startswith("@") else value
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise typer.BadParameter("--issues must be a JSON array or @file")
    return parsed

@app.command("get")
def get_issue(
    ctx: typer.Context,
    issue_key: str,
    fields: str = typer.Option("summary,status,assignee,reporter,priority", "--fields"),
    expand: str | None = typer.Option(None, "--expand"),
    comment_limit: int = typer.Option(10, "--comment-limit"),
    properties: str | None = typer.Option(None, "--properties"),
    update_history: bool = typer.Option(True, "--update-history"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = service.get(
        issue_key,
        fields=_parse_csv(fields),
        expand=expand,
        comment_limit=comment_limit,
        properties=_parse_csv(properties),
        update_history=update_history,
    )
    typer.echo(render_output(payload, output=output))

@app.command("create")
def create_issue(
    ctx: typer.Context,
    project_key: str = typer.Option(..., "--project-key"),
    summary: str = typer.Option(..., "--summary"),
    issue_type: str = typer.Option(..., "--issue-type"),
    assignee: str | None = typer.Option(None, "--assignee"),
    description: str | None = typer.Option(None, "--description"),
    components: str | None = typer.Option(None, "--components"),
    additional_fields: str | None = typer.Option(None, "--additional-fields"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = service.create(
        project_key=project_key,
        summary=summary,
        issue_type=issue_type,
        assignee=assignee,
        description=description,
        components=_parse_csv(components),
        additional_fields=_parse_json_option(additional_fields, option_name="--additional-fields"),
    )
    typer.echo(render_output(payload, output=output))

@app.command("update")
def update_issue(
    ctx: typer.Context,
    issue_key: str,
    fields: str = typer.Option(..., "--fields"),
    additional_fields: str | None = typer.Option(None, "--additional-fields"),
    components: str | None = typer.Option(None, "--components"),
    attachments: str | None = typer.Option(None, "--attachments"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    attachments_list = json.loads(attachments) if attachments else []
    payload = build_issue_service(ctx.obj).update(
        issue_key,
        fields=_parse_json_option(fields, option_name="--fields"),
        additional_fields=_parse_json_option(additional_fields, option_name="--additional-fields"),
        components=_parse_csv(components),
        attachments=attachments_list,
    )
    typer.echo(render_output(payload, output=output))

@app.command("batch-create")
def batch_create_issues(
    ctx: typer.Context,
    issues: str = typer.Option(..., "--issues"),
    validate_only: bool = typer.Option(False, "--validate-only"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    payload = build_issue_service(ctx.obj).batch_create(
        _parse_issue_batch(issues),
        validate_only=validate_only,
    )
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/jira/test_issue_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/commands/issue.py \
  tests/products/jira/test_issue_command.py
git commit -m "feat: align jira issue command inputs"
```

### Task 3: Expand Confluence Page Semantics In Provider, Service, And Schema Layers

**Files:**
- Modify: `src/atlassian_cli/products/confluence/providers/base.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `src/atlassian_cli/products/confluence/services/page.py`
- Modify: `src/atlassian_cli/products/confluence/schemas.py`
- Modify: `tests/products/confluence/test_page_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.confluence.services.page import PageService


class FakeSemanticPageProvider:
    def __init__(self) -> None:
        self.client = type("Client", (), {"url": "https://confluence.example.com"})()
        self.search_calls: list[dict] = []

    def get_page(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict:
        return {
            "id": page_id,
            "title": "Example Page",
            "type": "page",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": {"number": 7},
            "body": {"storage": {"value": "## Runbook\n\nUse the checklist."}},
        }

    def get_page_by_title(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict | None:
        assert space_key == "DEMO"
        assert title == "Example Page"
        return self.get_page("1234", include_metadata=include_metadata, convert_to_markdown=convert_to_markdown)

    def search_pages(self, query: str, *, limit: int, spaces_filter=None) -> list[dict]:
        self.search_calls.append({"query": query, "limit": limit, "spaces_filter": spaces_filter})
        return [self.get_page("1234")]

    def get_page_version(self, page_id: str, version: int, *, convert_to_markdown: bool = True) -> dict:
        return {
            "id": page_id,
            "title": "Example Page",
            "type": "page",
            "space": {"key": "DEMO", "name": "Demo Project"},
            "version": {"number": version},
            "body": {"storage": {"value": f"Version {version} body"}},
        }

    def create_page(
        self,
        *,
        space_key: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "markdown",
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict:
        return self.get_page("1235")

    def update_page(
        self,
        *,
        page_id: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "markdown",
        is_minor_edit: bool = False,
        version_comment: str | None = None,
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict:
        return self.get_page(page_id)


def test_page_service_search_passes_spaces_filter() -> None:
    provider = FakeSemanticPageProvider()
    service = PageService(provider=provider)

    result = service.search("label=documentation", limit=5, spaces_filter=["DEMO", "~example-user"])

    assert result["results"][0]["title"] == "Example Page"
    assert provider.search_calls == [
        {
            "query": "label=documentation",
            "limit": 5,
            "spaces_filter": ["DEMO", "~example-user"],
        }
    ]


def test_page_service_get_returns_metadata_and_content_envelope() -> None:
    service = PageService(provider=FakeSemanticPageProvider())

    result = service.get("1234", include_metadata=True, convert_to_markdown=True)

    assert result["metadata"]["id"] == "1234"
    assert result["content"]["value"] == "## Runbook\n\nUse the checklist."


def test_page_service_history_preserves_content_value() -> None:
    service = PageService(provider=FakeSemanticPageProvider())

    result = service.history("1234", version=2, convert_to_markdown=False)

    assert result["metadata"]["version"] == 2
    assert result["content"]["value"] == "Version 2 body"


def test_page_service_create_returns_message_and_page() -> None:
    service = PageService(provider=FakeSemanticPageProvider())

    result = service.create(
        space_key="DEMO",
        title="Example Page",
        content="## Runbook",
        parent_id="5678",
        content_format="markdown",
        enable_heading_anchors=True,
        include_content=False,
        emoji="📝",
    )

    assert result["message"] == "Page created successfully"
    assert result["page"]["id"] == "1235"


def test_page_service_update_returns_message_and_page() -> None:
    service = PageService(provider=FakeSemanticPageProvider())

    result = service.update(
        "1234",
        title="Example Page",
        content="## Runbook",
        parent_id="5678",
        content_format="markdown",
        is_minor_edit=True,
        version_comment="Example update",
        enable_heading_anchors=False,
        include_content=True,
        emoji=None,
    )

    assert result["message"] == "Page updated successfully"
    assert result["page"]["id"] == "1234"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/confluence/test_page_service.py -v`
Expected: FAIL because provider signatures and `PageService` still expose the old narrow read/write contract.

- [ ] **Step 3: Write minimal implementation**

```python
# src/atlassian_cli/products/confluence/providers/base.py
class ConfluenceProvider(Protocol):
    def get_page(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict:
        pass
    def get_page_by_title(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict | None:
        pass
    def search_pages(
        self,
        query: str,
        *,
        limit: int,
        spaces_filter: list[str] | None = None,
    ) -> list[dict]:
        pass
    def get_page_version(
        self,
        page_id: str,
        version: int,
        *,
        convert_to_markdown: bool = True,
    ) -> dict:
        pass
```

```python
# src/atlassian_cli/products/confluence/providers/server.py
def search_pages(self, query: str, *, limit: int, spaces_filter: list[str] | None = None) -> list[dict]:
    if query and not any(token in query for token in ("=", "~", " AND ", " OR ", ">", "<")):
        cql = f'siteSearch ~ {self._quote_cql_string(query)}'
    else:
        cql = query
    if spaces_filter:
        quoted = ", ".join(self._quote_cql_string(item) for item in spaces_filter)
        cql = f"space in ({quoted}) AND ({cql})"
    raw = self.client.cql(cql, limit=limit, expand="space,version,body.storage")
    return [item.get("content", item) for item in raw.get("results", []) if isinstance(item, dict)]

def get_page(
    self,
    page_id: str,
    *,
    include_metadata: bool = True,
    convert_to_markdown: bool = True,
) -> dict:
    expand = "space,version,body.storage" if include_metadata else "body.storage"
    return self.client.get_page_by_id(page_id, expand=expand)

def get_page_version(
    self,
    page_id: str,
    version: int,
    *,
    convert_to_markdown: bool = True,
) -> dict:
    return self.client.get_page_by_id(page_id, expand="space,version,body.storage", version=version)

def create_page(
    self,
    *,
    space_key: str,
    title: str,
    body: str,
    parent_id: str | None = None,
    content_format: str = "markdown",
    enable_heading_anchors: bool = False,
    emoji: str | None = None,
) -> dict:
    return self.client.create_page(space=space_key, title=title, body=body, parent_id=parent_id)

def update_page(
    self,
    *,
    page_id: str,
    title: str,
    body: str,
    parent_id: str | None = None,
    content_format: str = "markdown",
    is_minor_edit: bool = False,
    version_comment: str | None = None,
    enable_heading_anchors: bool = False,
    emoji: str | None = None,
) -> dict:
    return self.client.update_page(page_id=page_id, title=title, body=body, parent_id=parent_id)
```

```python
# src/atlassian_cli/products/confluence/services/page.py
def _page_envelope(self, payload: dict, *, include_metadata: bool = True, include_content: bool = True) -> dict:
    page = ConfluencePage.from_api_response(payload, **self._page_kwargs())
    result: dict[str, object] = {}
    if include_metadata:
        result["metadata"] = page.to_simplified_dict()
    if include_content and page.content not in (None, ""):
        result["content"] = {"value": page.content}
    return result

def get(
    self,
    page_id: str,
    *,
    include_metadata: bool = True,
    convert_to_markdown: bool = True,
) -> dict:
    raw = self.provider.get_page(
        page_id,
        include_metadata=include_metadata,
        convert_to_markdown=convert_to_markdown,
    )
    return self._page_envelope(raw, include_metadata=include_metadata, include_content=True)

def search(self, query: str, *, limit: int, spaces_filter: list[str] | None = None) -> dict:
    return {
        "results": [
            ConfluencePage.from_api_response(item, **self._page_kwargs()).to_simplified_dict()
            for item in self.provider.search_pages(query, limit=limit, spaces_filter=spaces_filter)
        ]
    }

def history(
    self,
    page_id: str,
    *,
    version: int,
    convert_to_markdown: bool = True,
) -> dict:
    raw = self.provider.get_page_version(page_id, version, convert_to_markdown=convert_to_markdown)
    return self._page_envelope(raw, include_metadata=True, include_content=True)

def create(
    self,
    *,
    space_key: str,
    title: str,
    content: str,
    parent_id: str | None,
    content_format: str,
    enable_heading_anchors: bool,
    include_content: bool,
    emoji: str | None,
) -> dict:
    raw = self.provider.create_page(
        space_key=space_key,
        title=title,
        body=content,
        parent_id=parent_id,
        content_format=content_format,
        enable_heading_anchors=enable_heading_anchors,
        emoji=emoji,
    )
    page = ConfluencePage.from_api_response(raw, **self._page_kwargs()).to_simplified_dict()
    return {"message": "Page created successfully", "page": page if not include_content else self._page_envelope(raw)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/confluence/test_page_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/confluence/providers/base.py \
  src/atlassian_cli/products/confluence/providers/server.py \
  src/atlassian_cli/products/confluence/services/page.py \
  src/atlassian_cli/products/confluence/schemas.py \
  tests/products/confluence/test_page_service.py
git commit -m "feat: align confluence page service semantics"
```

### Task 4: Rework Confluence Page Commands And Markdown Envelope Rendering

**Files:**
- Modify: `src/atlassian_cli/products/confluence/commands/page.py`
- Modify: `src/atlassian_cli/output/markdown.py`
- Modify: `tests/products/confluence/test_page_command.py`
- Modify: `tests/output/test_markdown.py`

- [ ] **Step 1: Write the failing tests**

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.output.markdown import render_markdown

runner = CliRunner()


def test_confluence_page_search_accepts_spaces_filter(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    captured: dict[str, object] = {}

    class FakeService:
        def search(self, query, *, limit, spaces_filter=None):
            captured["query"] = query
            captured["limit"] = limit
            captured["spaces_filter"] = spaces_filter
            return {"results": [{"id": "1234", "title": "Example Page"}]}

    monkeypatch.setattr(page_module, "build_page_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "search",
            "--query",
            "label=documentation",
            "--spaces-filter",
            "DEMO,~example-user",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["spaces_filter"] == ["DEMO", "~example-user"]


def test_confluence_page_get_supports_metadata_and_markdown_flags(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    captured: dict[str, object] = {}

    class FakeService:
        def get(self, page_id, **kwargs):
            captured["page_id"] = page_id
            captured["kwargs"] = kwargs
            return {"metadata": {"id": page_id}, "content": {"value": "Example body"}}

    monkeypatch.setattr(page_module, "build_page_service", lambda *_args, **_kwargs: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://confluence.example.com",
            "confluence",
            "page",
            "get",
            "1234",
            "--include-metadata",
            "--convert-to-markdown",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["kwargs"] == {"include_metadata": True, "convert_to_markdown": True}


def test_render_markdown_unwraps_message_plus_issue_envelope() -> None:
    rendered = render_markdown(
        {
            "message": "Issue created successfully",
            "issue": {
                "key": "DEMO-1",
                "summary": "Example issue summary",
                "status": {"name": "Open"},
            },
        }
    )

    assert rendered.startswith("# DEMO-1 - Example issue summary")
    assert "- Status: Open" in rendered


def test_render_markdown_renders_page_metadata_and_content_envelope() -> None:
    rendered = render_markdown(
        {
            "metadata": {"id": "1234", "title": "Example Page", "version": 2},
            "content": {"value": "## Runbook\n\nUse the checklist."},
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
    assert "Use the checklist." in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/confluence/test_page_command.py tests/output/test_markdown.py -v`
Expected: FAIL because command options and markdown rendering do not yet understand MCP-like envelopes.

- [ ] **Step 3: Write minimal implementation**

```python
# src/atlassian_cli/products/confluence/commands/page.py
def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    values = [item.strip() for item in value.split(",") if item.strip()]
    return values or None

@app.command("search")
def search_pages(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    limit: int = typer.Option(25, "--limit"),
    spaces_filter: str | None = typer.Option(None, "--spaces-filter"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    payload = build_page_service(ctx.obj).search(
        query,
        limit=limit,
        spaces_filter=_parse_csv(spaces_filter),
    )
    typer.echo(render_output(payload, output=output))

@app.command("get")
def get_page(
    ctx: typer.Context,
    page_id: str | None = typer.Argument(None),
    title: str | None = typer.Option(None, "--title"),
    space_key: str | None = typer.Option(None, "--space-key"),
    include_metadata: bool = typer.Option(True, "--include-metadata"),
    convert_to_markdown: bool = typer.Option(True, "--convert-to-markdown"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    if page_id is not None:
        payload = service.get(
            page_id,
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )
    elif title and space_key:
        payload = service.get_by_title(
            space_key,
            title,
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )
    else:
        raise typer.BadParameter("provide a page id or both --title and --space-key")
    typer.echo(render_output(payload, output=output))

@app.command("create")
def create_page(
    ctx: typer.Context,
    space_key: str = typer.Option(..., "--space-key"),
    title: str = typer.Option(..., "--title"),
    content: str = typer.Option(..., "--content"),
    parent_id: str | None = typer.Option(None, "--parent-id"),
    content_format: str = typer.Option("markdown", "--content-format"),
    enable_heading_anchors: bool = typer.Option(False, "--enable-heading-anchors"),
    include_content: bool = typer.Option(False, "--include-content"),
    emoji: str | None = typer.Option(None, "--emoji"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    payload = build_page_service(ctx.obj).create(
        space_key=space_key,
        title=title,
        content=content,
        parent_id=parent_id,
        content_format=content_format,
        enable_heading_anchors=enable_heading_anchors,
        include_content=include_content,
        emoji=emoji,
    )
    typer.echo(render_output(payload, output=output))
```

```python
# src/atlassian_cli/output/markdown.py
def _unwrap_record(value: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("issue", "page"):
        candidate = value.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    if isinstance(value.get("metadata"), Mapping):
        record = dict(value["metadata"])
        content = value.get("content")
        if isinstance(content, Mapping) and content.get("value") not in (None, ""):
            record["content"] = content["value"]
        return record
    return value

def render_markdown(value: Any) -> str:
    items = _collection_items(value)
    if items:
        blocks: list[str] = []
        for index, item in enumerate(items, start=1):
            lines = [f"{index}. {_heading(item)}"]
            for field, label in (
                ("state", "State"),
                ("status", "Status"),
                ("author", "Author"),
                ("assignee", "Assignee"),
                ("reviewers", "Reviewers"),
                ("from_ref", "From"),
                ("to_ref", "To"),
                ("updated", "Updated"),
                ("updated_date", "Updated"),
            ):
                text = _inline_value(item.get(field))
                if text:
                    lines.append(f"   - {label}: {text}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
    if not isinstance(value, Mapping):
        return _inline_value(value)
    value = _unwrap_record(value)
    lines = [f"# {_heading(value)}"]
    for field, label in (
        ("state", "State"),
        ("status", "Status"),
        ("author", "Author"),
        ("assignee", "Assignee"),
        ("reporter", "Reporter"),
        ("created", "Created"),
        ("updated", "Updated"),
    ):
        text = _inline_value(value.get(field))
        if text:
            lines.append(f"- {label}: {text}")
    for field in DETAIL_BODY_FIELDS:
        text = _inline_value(value.get(field))
        if text:
            lines.extend(["", f"## {field.title()}", text])
    return "\n".join(lines).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/products/confluence/test_page_command.py tests/output/test_markdown.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/confluence/commands/page.py \
  src/atlassian_cli/output/markdown.py \
  tests/products/confluence/test_page_command.py \
  tests/output/test_markdown.py
git commit -m "feat: align confluence page command inputs"
```

### Task 5: Add Live E2E Discovery Helpers And Adapt Live Suites

**Files:**
- Create: `tests/e2e/support/discovery.py`
- Modify: `tests/e2e/support/__init__.py`
- Modify: `tests/e2e/support/env.py`
- Modify: `tests/e2e/test_jira_live.py`
- Modify: `tests/e2e/test_confluence_live.py`
- Modify: `tests/e2e/test_bitbucket_live.py`
- Modify: `tests/e2e/test_support.py`

- [ ] **Step 1: Write the failing tests**

```python
from tests.e2e.support.discovery import (
    build_jira_create_payload,
    resolve_bitbucket_repo_target,
    resolve_confluence_write_target,
)
from tests.e2e.support.env import LiveEnv


class FakeJiraProvider:
    class Client:
        def issue_createmeta(self, project_key, expand):
            assert project_key == "DEMO"
            assert expand == "projects.issuetypes.fields"
            return {
                "projects": [
                    {
                        "issuetypes": [
                            {
                                "name": "Task",
                                "fields": {
                                    "summary": {"required": True},
                                    "customfield_10001": {
                                        "required": True,
                                        "allowedValues": [{"id": "11", "value": "Linux"}],
                                    },
                                },
                            }
                        ]
                    }
                ]
            }

    def __init__(self) -> None:
        self.client = self.Client()


def test_build_jira_create_payload_uses_allowed_value_defaults() -> None:
    payload = build_jira_create_payload(
        FakeJiraProvider(),
        project_key="DEMO",
        summary="Example issue summary",
        issue_type="Task",
        env_overrides={},
    )

    assert payload["project"]["key"] == "DEMO"
    assert payload["customfield_10001"] == {"id": "11"}


def test_resolve_confluence_write_target_prefers_explicit_parent() -> None:
    env = LiveEnv(
        config_file=None,  # type: ignore[arg-type]
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
        confluence_parent_page="1234",
    )

    target = resolve_confluence_write_target(env)

    assert target == {"space_key": "~example-user", "parent_page_id": "1234"}


def test_resolve_bitbucket_repo_target_uses_override_when_present() -> None:
    env = LiveEnv(
        config_file=None,  # type: ignore[arg-type]
        jira_project="DEMO",
        confluence_space="~example-user",
        bitbucket_project="DEMO",
        bitbucket_create_project="DEMO",
        bitbucket_repo="example-repo",
        bitbucket_existing_repo="sandbox-repo",
    )

    target = resolve_bitbucket_repo_target(env)

    assert target == {"project_key": "DEMO", "repo_slug": "sandbox-repo"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/e2e/test_support.py -v`
Expected: FAIL with import errors because the discovery helpers and expanded `LiveEnv` fields do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# tests/e2e/support/env.py
@dataclass(frozen=True)
class LiveEnv:
    config_file: Path
    jira_project: str
    confluence_space: str
    bitbucket_project: str
    bitbucket_create_project: str
    bitbucket_repo: str
    jira_issue_type: str | None = None
    confluence_parent_page: str | None = None
    bitbucket_existing_repo: str | None = None

def load_live_env() -> LiveEnv:
    return LiveEnv(
        config_file=config_file,
        jira_project=os.getenv("ATLASSIAN_E2E_JIRA_PROJECT", "DEMO"),
        confluence_space=os.getenv("ATLASSIAN_E2E_CONFLUENCE_SPACE", "~example-user"),
        bitbucket_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_PROJECT", "DEMO"),
        bitbucket_create_project=os.getenv("ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT", "DEMO"),
        bitbucket_repo=os.getenv("ATLASSIAN_E2E_BITBUCKET_REPO", "example-repo"),
        jira_issue_type=os.getenv("ATLASSIAN_E2E_JIRA_ISSUE_TYPE"),
        confluence_parent_page=os.getenv("ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE"),
        bitbucket_existing_repo=os.getenv("ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO"),
    )
```

```python
# tests/e2e/support/discovery.py
def build_jira_create_payload(provider, *, project_key: str, summary: str, issue_type: str, env_overrides: dict[str, str]) -> dict:
    meta = provider.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
    issue_types = meta.get("projects", [{}])[0].get("issuetypes", [])
    selected = next(item for item in issue_types if item.get("name") == issue_type)
    payload = {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    for field_id, info in selected.get("fields", {}).items():
        if field_id in {"project", "issuetype", "summary", "description"}:
            continue
        if not info.get("required"):
            continue
        if field_id in env_overrides:
            payload[field_id] = json.loads(env_overrides[field_id])
            continue
        allowed = info.get("allowedValues") or []
        if allowed:
            chosen = allowed[0]
            payload[field_id] = {"id": chosen["id"]} if chosen.get("id") else chosen
            continue
        raise RuntimeError(f"missing required test value for {field_id}")
    return payload

def resolve_confluence_write_target(live_env: LiveEnv) -> dict[str, str | None]:
    return {
        "space_key": live_env.confluence_space,
        "parent_page_id": live_env.confluence_parent_page,
    }

def resolve_bitbucket_repo_target(live_env: LiveEnv) -> dict[str, str]:
    return {
        "project_key": live_env.bitbucket_project,
        "repo_slug": live_env.bitbucket_existing_repo or live_env.bitbucket_repo,
    }
```

```python
# tests/e2e/test_jira_live.py
provider = build_live_provider(Product.JIRA, live_env)
issue_type = live_env.jira_issue_type or "Task"
payload = build_jira_create_payload(
    provider,
    project_key=live_env.jira_project,
    summary=summary,
    issue_type=issue_type,
    env_overrides={},
)
payload["description"] = "created by live e2e"
created = run_json(
    live_env,
    "jira",
    "issue",
    "create",
    "--project-key",
    live_env.jira_project,
    "--issue-type",
    issue_type,
    "--summary",
    payload["summary"],
    "--description",
    payload["description"],
    "--additional-fields",
    json.dumps({k: v for k, v in payload.items() if k not in {"project", "issuetype", "summary", "description"}}),
    "--output",
    "json",
)
```

```python
# tests/e2e/test_confluence_live.py
target = resolve_confluence_write_target(live_env)
page = run_json(
    live_env,
    "confluence",
    "page",
    "create",
    "--space-key",
    str(target["space_key"]),
    "--title",
    unique_name("confluence-page"),
    "--content",
    "<p>version one</p>",
    *(["--parent-id", str(target["parent_page_id"])] if target["parent_page_id"] else []),
    "--output",
    "json",
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/e2e/test_support.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/support/discovery.py \
  tests/e2e/support/__init__.py \
  tests/e2e/support/env.py \
  tests/e2e/test_jira_live.py \
  tests/e2e/test_confluence_live.py \
  tests/e2e/test_bitbucket_live.py \
  tests/e2e/test_support.py
git commit -m "test: harden live e2e discovery"
```

### Task 6: Update Public Docs And Run Repository Verification

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `tests/test_readme.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_readme_mentions_semantic_alignment_and_output_breaking_change() -> None:
    readme = Path("README.md").read_text()

    assert "TOOLSETS=default" in readme
    assert "normalized json and yaml output now follows MCP-style resource envelopes" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme


def test_contributing_mentions_new_live_e2e_env_overrides() -> None:
    contributing = Path("CONTRIBUTING.md").read_text()

    assert "ATLASSIAN_E2E_JIRA_ISSUE_TYPE" in contributing
    assert "ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO" in contributing
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_readme.py -v`
Expected: FAIL because the docs do not yet describe the new normalized-output contract or the new e2e environment variables.

- [ ] **Step 3: Write minimal implementation**

```markdown
<!-- README.md -->
## Scope

The CLI aligns its Jira and Confluence default command groups with `mcp-atlassian` `TOOLSETS=default` for Server and Data Center:

- Jira issues, fields, comments, and transitions
- Confluence pages and comments

Normalized `json` and `yaml` output now follows MCP-style resource envelopes more closely. This is a breaking change for scripts that consumed older normalized output.

Stable raw modes:

- `raw-json`
- `raw-yaml`
```

```markdown
<!-- CONTRIBUTING.md -->
Additional live e2e overrides:

- `ATLASSIAN_E2E_JIRA_ISSUE_TYPE=Task`
- `ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE=123456`
- `ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO=example-repo`

Use these when the target instance requires a specific issue type, only allows page creation under a known parent, or does not provide a stable shared seed repository.
```

- [ ] **Step 4: Run repository verification**

Run:

```bash
PYTHONPATH=src .venv/bin/ruff format --check .
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected:

- `ruff format --check .` exits 0
- `pytest -q` exits 0
- `ruff check README.md pyproject.toml src tests docs` exits 0

- [ ] **Step 5: Commit**

```bash
git add README.md CONTRIBUTING.md tests/test_readme.py
git commit -m "docs: describe semantic alignment output changes"
```
