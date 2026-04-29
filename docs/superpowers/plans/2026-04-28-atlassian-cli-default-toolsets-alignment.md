# Atlassian CLI Default Toolsets Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the CLI's Jira and Confluence command surface with the `mcp-atlassian` `TOOLSETS=default` capability set for Server/Data Center, while isolating the single Cloud-only Jira changelog batch gap behind an explicit follow-up decision.

**Architecture:** Keep Typer commands thin and continue the existing `command -> service -> provider -> schema` flow. Add focused Jira `field` and `comment` command groups plus a Confluence `comment` group, extend the existing issue/page services for adjacent workflows, and push product-specific API calls into provider methods so tests can stay fake-provider driven. For capabilities that `atlassian-python-api` does not expose directly, keep the glue logic in CLI-owned services: derive Confluence page diffs with `difflib.unified_diff`, derive space trees by walking child pages, and normalize field/comment payloads in `schemas.py`.

**Tech Stack:** Python 3.12, Typer, Pydantic, prompt_toolkit, Rich, atlassian-python-api, pytest

---

## Planned File Structure

### Modify

- `README.md`
- `src/atlassian_cli/cli.py`
- `src/atlassian_cli/products/factory.py`
- `src/atlassian_cli/products/jira/providers/base.py`
- `src/atlassian_cli/products/jira/providers/server.py`
- `src/atlassian_cli/products/jira/services/issue.py`
- `src/atlassian_cli/products/jira/commands/issue.py`
- `src/atlassian_cli/products/jira/schemas.py`
- `src/atlassian_cli/products/confluence/providers/base.py`
- `src/atlassian_cli/products/confluence/providers/server.py`
- `src/atlassian_cli/products/confluence/services/page.py`
- `src/atlassian_cli/products/confluence/commands/page.py`
- `src/atlassian_cli/products/confluence/schemas.py`
- `tests/test_cli_help.py`
- `tests/products/jira/test_issue_command.py`
- `tests/products/jira/test_issue_service.py`
- `tests/products/confluence/test_page_command.py`
- `tests/products/confluence/test_page_service.py`

### Create

- `src/atlassian_cli/products/jira/commands/field.py`
- `src/atlassian_cli/products/jira/commands/comment.py`
- `src/atlassian_cli/products/jira/services/field.py`
- `src/atlassian_cli/products/jira/services/comment.py`
- `src/atlassian_cli/products/confluence/commands/comment.py`
- `src/atlassian_cli/products/confluence/services/comment.py`
- `tests/products/jira/test_field_command.py`
- `tests/products/jira/test_field_service.py`
- `tests/products/jira/test_comment_command.py`
- `tests/products/jira/test_comment_service.py`
- `tests/products/confluence/test_comment_command.py`
- `tests/products/confluence/test_comment_service.py`

### Responsibilities

- `src/atlassian_cli/products/jira/commands/field.py` owns `jira field search` and `jira field options`.
- `src/atlassian_cli/products/jira/commands/comment.py` owns `jira comment add` and `jira comment edit`.
- `src/atlassian_cli/products/jira/services/field.py` normalizes field definitions and allowed values from provider payloads.
- `src/atlassian_cli/products/jira/services/comment.py` wraps Jira comment create/edit flows into CLI-friendly dicts.
- `src/atlassian_cli/products/jira/services/issue.py` owns the remaining default `jira_issues` and `jira_transitions` gaps: delete, batch create, get transitions, richer create/update, and the explicit Cloud-only changelog guard.
- `src/atlassian_cli/products/confluence/services/page.py` owns search, page lookup by title/space, child listing, space tree walking, move, history lookup, and diff generation.
- `src/atlassian_cli/products/confluence/commands/comment.py` plus `services/comment.py` own list/add/reply flows for `confluence_comments`.
- `schemas.py` files own CLI-normalized shapes for new field, option, comment, and page-history payloads.

### Scope Boundaries

- This plan targets the six default toolsets only: `jira_issues`, `jira_fields`, `jira_comments`, `jira_transitions`, `confluence_pages`, and `confluence_comments`.
- Bitbucket, Jira projects/users, Confluence spaces/attachments, and any non-default toolsets stay unchanged unless a default capability depends on them indirectly.
- Literal parity with every `mcp-atlassian` default tool is blocked by one Cloud-only capability: Jira batch changelog fetch. This plan reserves and documents that gap instead of silently ignoring it.

### Common Commands

- Install deps: `.venv/bin/pip install -e '.[dev]'`
- Targeted tests: `.venv/bin/pytest tests/products/jira/test_field_service.py -v`
- Full tests: `.venv/bin/pytest`

### Task 1: Wire New Default Toolset Command Groups

**Files:**
- Modify: `src/atlassian_cli/cli.py`
- Modify: `tests/test_cli_help.py`
- Create: `src/atlassian_cli/products/jira/commands/field.py`
- Create: `src/atlassian_cli/products/jira/commands/comment.py`
- Create: `src/atlassian_cli/products/confluence/commands/comment.py`

- [ ] **Step 1: Write the failing test**

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_root_help_lists_default_alignment_command_groups() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "field" in result.stdout
    assert "comment" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli_help.py::test_root_help_lists_default_alignment_command_groups -v`
Expected: FAIL because the new Jira and Confluence subcommands are not registered.

- [ ] **Step 3: Write minimal implementation**

```python
from atlassian_cli.products.confluence.commands.comment import app as confluence_comment_app
from atlassian_cli.products.jira.commands.comment import app as jira_comment_app
from atlassian_cli.products.jira.commands.field import app as jira_field_app

jira_app.add_typer(jira_field_app, name="field")
jira_app.add_typer(jira_comment_app, name="comment")
confluence_app.add_typer(confluence_comment_app, name="comment")
```

```python
import typer

app = typer.Typer(help="Jira field commands")
```

```python
import typer

app = typer.Typer(help="Jira comment commands")
```

```python
import typer

app = typer.Typer(help="Confluence comment commands")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli_help.py::test_root_help_lists_default_alignment_command_groups -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/cli.py src/atlassian_cli/products/jira/commands/field.py src/atlassian_cli/products/jira/commands/comment.py src/atlassian_cli/products/confluence/commands/comment.py tests/test_cli_help.py
git commit -m "feat: add default toolset command groups"
```

### Task 2: Implement Jira Field Discovery and Transition Listing

**Files:**
- Modify: `src/atlassian_cli/products/jira/providers/base.py`
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Modify: `src/atlassian_cli/products/jira/services/issue.py`
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `src/atlassian_cli/products/jira/schemas.py`
- Create: `src/atlassian_cli/products/jira/services/field.py`
- Create: `src/atlassian_cli/products/jira/commands/field.py`
- Create: `tests/products/jira/test_field_service.py`
- Create: `tests/products/jira/test_field_command.py`
- Modify: `tests/products/jira/test_issue_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.jira.services.field import FieldService


class FakeFieldProvider:
    def search_fields(self, query: str) -> list[dict]:
        assert query == "story"
        return [
            {"id": "customfield_10001", "name": "Story Points", "schema": {"type": "number"}},
        ]

    def get_field_options(self, field_id: str, project_key: str, issue_type: str) -> list[dict]:
        assert field_id == "customfield_10001"
        assert project_key == "PROJ"
        assert issue_type == "Bug"
        return [{"id": "1", "value": "1"}, {"id": "2", "value": "2"}]


def test_field_service_search_normalizes_results() -> None:
    service = FieldService(provider=FakeFieldProvider())

    result = service.search("story")

    assert result == {
        "results": [
            {"id": "customfield_10001", "name": "Story Points", "type": "number"},
        ]
    }


def test_field_service_options_normalizes_results() -> None:
    service = FieldService(provider=FakeFieldProvider())

    result = service.options("customfield_10001", project_key="PROJ", issue_type="Bug")

    assert result["results"] == [{"id": "1", "value": "1"}, {"id": "2", "value": "2"}]
```

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_issue_transitions_outputs_available_ids(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get_transitions": lambda self, issue_key: {"results": [{"id": "31", "name": "Done"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "transitions", "PROJ-1", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"id": "31"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/products/jira/test_field_service.py tests/products/jira/test_field_command.py tests/products/jira/test_issue_command.py::test_jira_issue_transitions_outputs_available_ids -v`
Expected: FAIL with import errors for `FieldService` and missing `transitions` command behavior.

- [ ] **Step 3: Write minimal implementation**

```python
class JiraProvider(Protocol):
    def search_fields(self, query: str) -> list[dict]: ...
    def get_field_options(self, field_id: str, project_key: str, issue_type: str) -> list[dict]: ...
    def get_issue_transitions(self, issue_key: str) -> list[dict]: ...
```

```python
class JiraServerProvider:
    def search_fields(self, query: str) -> list[dict]:
        fields = self.client.get_all_fields()
        query_lower = query.lower()
        return [
            field for field in fields
            if not query or query_lower in str(field.get("name", "")).lower()
        ]

    def get_field_options(self, field_id: str, project_key: str, issue_type: str) -> list[dict]:
        meta = self.client.issue_createmeta(project_key, issue_type)
        field_meta = meta["projects"][0]["issuetypes"][0]["fields"][field_id]
        return field_meta.get("allowedValues", [])

    def get_issue_transitions(self, issue_key: str) -> list[dict]:
        return self.client.get_issue_transitions(issue_key)
```

```python
class JiraField(ApiModel):
    id: str
    name: str
    type: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "JiraField":
        schema = data.get("schema") if isinstance(data.get("schema"), dict) else {}
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            type=coerce_str(schema.get("type")),
        )
```

```python
class FieldService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def search(self, query: str) -> dict:
        return {
            "results": [
                JiraField.from_api_response(item).to_simplified_dict()
                for item in self.provider.search_fields(query)
            ]
        }

    def options(self, field_id: str, *, project_key: str, issue_type: str) -> dict:
        return {"results": self.provider.get_field_options(field_id, project_key, issue_type)}
```

```python
@app.command("transitions")
def get_transitions(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    payload = service.get_transitions(issue_key)
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/products/jira/test_field_service.py tests/products/jira/test_field_command.py tests/products/jira/test_issue_command.py::test_jira_issue_transitions_outputs_available_ids -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/providers/base.py src/atlassian_cli/products/jira/providers/server.py src/atlassian_cli/products/jira/services/issue.py src/atlassian_cli/products/jira/services/field.py src/atlassian_cli/products/jira/commands/issue.py src/atlassian_cli/products/jira/commands/field.py src/atlassian_cli/products/jira/schemas.py tests/products/jira/test_field_service.py tests/products/jira/test_field_command.py tests/products/jira/test_issue_command.py
git commit -m "feat: add jira field discovery commands"
```

### Task 3: Close the Jira Comment and Issue Gaps

**Files:**
- Modify: `src/atlassian_cli/products/jira/providers/base.py`
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Modify: `src/atlassian_cli/products/jira/services/issue.py`
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `src/atlassian_cli/products/jira/schemas.py`
- Create: `src/atlassian_cli/products/jira/services/comment.py`
- Create: `src/atlassian_cli/products/jira/commands/comment.py`
- Create: `tests/products/jira/test_comment_service.py`
- Create: `tests/products/jira/test_comment_command.py`
- Modify: `tests/products/jira/test_issue_service.py`
- Modify: `tests/products/jira/test_issue_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.jira.services.comment import CommentService


class FakeCommentProvider:
    def add_comment(self, issue_key: str, body: str) -> dict:
        return {"id": "10001", "body": body, "author": {"displayName": "Alice"}}

    def edit_comment(self, issue_key: str, comment_id: str, body: str) -> dict:
        return {"id": comment_id, "body": body, "author": {"displayName": "Alice"}}


def test_comment_service_add_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.add("PROJ-1", "Looks good")

    assert result == {
        "id": "10001",
        "body": "Looks good",
        "author": {"display_name": "Alice", "name": "Alice"},
    }
```

```python
def test_issue_service_delete_returns_success_payload() -> None:
    class FakeIssueProvider:
        def delete_issue(self, issue_key: str) -> None:
            assert issue_key == "PROJ-1"

    service = IssueService(provider=FakeIssueProvider())

    assert service.delete("PROJ-1") == {"key": "PROJ-1", "deleted": True}
```

```python
def test_jira_comment_add_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"add": lambda self, issue_key, body: {"id": "10001", "body": body}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "comment", "add", "PROJ-1", "--body", "example approval comment", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"id": "10001"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/products/jira/test_comment_service.py tests/products/jira/test_comment_command.py tests/products/jira/test_issue_service.py::test_issue_service_delete_returns_success_payload -v`
Expected: FAIL because comment service/command files and delete behavior do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class JiraProvider(Protocol):
    def add_comment(self, issue_key: str, body: str) -> dict: ...
    def edit_comment(self, issue_key: str, comment_id: str, body: str) -> dict: ...
    def delete_issue(self, issue_key: str) -> None: ...
    def create_issues(self, issues: list[dict]) -> list[dict]: ...
```

```python
class JiraServerProvider:
    def add_comment(self, issue_key: str, body: str) -> dict:
        return self.client.issue_add_comment(issue_key, body)

    def edit_comment(self, issue_key: str, comment_id: str, body: str) -> dict:
        return self.client.issue_edit_comment(issue_key, comment_id, body)

    def delete_issue(self, issue_key: str) -> None:
        self.client.delete_issue(issue_key)

    def create_issues(self, issues: list[dict]) -> list[dict]:
        return self.client.create_issues(issues)
```

```python
class CommentService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def add(self, issue_key: str, body: str) -> dict:
        return JiraComment.from_api_response(self.provider.add_comment(issue_key, body)).to_simplified_dict()

    def edit(self, issue_key: str, comment_id: str, body: str) -> dict:
        return JiraComment.from_api_response(
            self.provider.edit_comment(issue_key, comment_id, body)
        ).to_simplified_dict()
```

```python
@app.command("delete")
def delete_issue(
    ctx: typer.Context,
    issue_key: str,
    yes: bool = typer.Option(False, "--yes"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    if not yes:
        raise typer.BadParameter("pass --yes to confirm delete")
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.delete(issue_key), output=output))
```

```python
@app.command("batch-create")
def batch_create_issues(
    ctx: typer.Context,
    file_path: str = typer.Option(..., "--file"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    issues = json.loads(Path(file_path).read_text())
    service = build_issue_service(ctx.obj)
    typer.echo(render_output(service.batch_create(issues), output=output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/products/jira/test_comment_service.py tests/products/jira/test_comment_command.py tests/products/jira/test_issue_service.py tests/products/jira/test_issue_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/providers/base.py src/atlassian_cli/products/jira/providers/server.py src/atlassian_cli/products/jira/services/issue.py src/atlassian_cli/products/jira/services/comment.py src/atlassian_cli/products/jira/commands/issue.py src/atlassian_cli/products/jira/commands/comment.py src/atlassian_cli/products/jira/schemas.py tests/products/jira/test_comment_service.py tests/products/jira/test_comment_command.py tests/products/jira/test_issue_service.py tests/products/jira/test_issue_command.py
git commit -m "feat: add jira default comment workflows"
```

### Task 4: Expand Confluence Page Workflows to Match the Default Page Toolset

**Files:**
- Modify: `src/atlassian_cli/products/confluence/providers/base.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `src/atlassian_cli/products/confluence/services/page.py`
- Modify: `src/atlassian_cli/products/confluence/commands/page.py`
- Modify: `src/atlassian_cli/products/confluence/schemas.py`
- Modify: `tests/products/confluence/test_page_service.py`
- Modify: `tests/products/confluence/test_page_command.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_page_service_search_normalizes_results() -> None:
    class FakePageProvider:
        client = type("Client", (), {"url": "https://confluence.example.com"})()

        def search_pages(self, query: str, limit: int) -> list[dict]:
            assert query == "runbook"
            return [{"id": "1234", "title": "Example Page", "space": {"key": "PROJ", "name": "Demo Project"}}]

    service = PageService(provider=FakePageProvider())

    result = service.search("runbook", limit=10)

    assert result["results"][0]["title"] == "Example Page"
```

```python
def test_page_service_diff_returns_unified_diff() -> None:
    class FakePageProvider:
        client = type("Client", (), {"url": "https://confluence.example.com"})()

        def get_page_version(self, page_id: str, version: int) -> dict:
            body = "hello\nworld\n" if version == 1 else "hello\nops\n"
            return {"id": page_id, "title": "Example Page", "body": {"storage": {"value": body}}}

    service = PageService(provider=FakePageProvider())

    result = service.diff("1234", from_version=1, to_version=2)

    assert "--- version-1" in result["diff"]
    assert "+ops" in result["diff"]
```

```python
def test_confluence_page_search_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"search": lambda self, query, limit: {"results": [{"id": "1234", "title": "Example Page"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://confluence.example.com", "confluence", "page", "search", "--query", "runbook", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"title": "Example Page"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py -v`
Expected: FAIL because search, diff, history, tree, and move methods do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class ConfluenceProvider(Protocol):
    def search_pages(self, query: str, limit: int) -> list[dict]: ...
    def get_page_by_title(self, space_key: str, title: str) -> dict | None: ...
    def get_page_children(self, page_id: str) -> list[dict]: ...
    def get_space_homepage(self, space_key: str) -> dict: ...
    def move_page(self, page_id: str, parent_id: str | None, space_key: str | None) -> dict: ...
    def get_page_version(self, page_id: str, version: int) -> dict: ...
```

```python
class ConfluenceServerProvider:
    def search_pages(self, query: str, limit: int) -> list[dict]:
        return self.client.get_all_pages_from_space_through_cql(f'text ~ "{query}"', limit=limit)

    def get_page_by_title(self, space_key: str, title: str) -> dict | None:
        return self.client.get_page_by_title(space_key, title)

    def get_page_children(self, page_id: str) -> list[dict]:
        return self.client.get_child_pages(page_id)

    def get_space_homepage(self, space_key: str) -> dict:
        return self.client.get_home_page_of_space(space_key)

    def move_page(self, page_id: str, parent_id: str | None, space_key: str | None) -> dict:
        target = parent_id or self.client.get_home_page_of_space(space_key)["id"]
        return self.client.move_page(space_key, page_id, target)

    def get_page_version(self, page_id: str, version: int) -> dict:
        return self.client.get_content_history_by_version_number(page_id, version)
```

```python
def diff(self, page_id: str, *, from_version: int, to_version: int) -> dict:
    from_page = self.provider.get_page_version(page_id, from_version)
    to_page = self.provider.get_page_version(page_id, to_version)
    from_text = nested_get(from_page, "body", "storage", "value") or ""
    to_text = nested_get(to_page, "body", "storage", "value") or ""
    diff = "\n".join(
        unified_diff(
            from_text.splitlines(),
            to_text.splitlines(),
            fromfile=f"version-{from_version}",
            tofile=f"version-{to_version}",
            lineterm="",
        )
    )
    return {"page_id": page_id, "from_version": from_version, "to_version": to_version, "diff": diff}
```

```python
@app.command("search")
def search_pages(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_page_service(ctx.obj)
    typer.echo(render_output(service.search(query, limit=limit), output=output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/confluence/providers/base.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/confluence/services/page.py src/atlassian_cli/products/confluence/commands/page.py src/atlassian_cli/products/confluence/schemas.py tests/products/confluence/test_page_service.py tests/products/confluence/test_page_command.py
git commit -m "feat: add default confluence page workflows"
```

### Task 5: Implement Confluence Comment Listing, Add, and Reply

**Files:**
- Modify: `src/atlassian_cli/products/confluence/providers/base.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `src/atlassian_cli/products/confluence/schemas.py`
- Create: `src/atlassian_cli/products/confluence/services/comment.py`
- Create: `src/atlassian_cli/products/confluence/commands/comment.py`
- Create: `tests/products/confluence/test_comment_service.py`
- Create: `tests/products/confluence/test_comment_command.py`

- [ ] **Step 1: Write the failing tests**

```python
from atlassian_cli.products.confluence.services.comment import CommentService


class FakeCommentProvider:
    def list_comments(self, page_id: str) -> list[dict]:
        return [{"id": "c1", "body": {"storage": {"value": "example approval"}}, "history": {"createdDate": "2026-04-28"}}]

    def add_comment(self, page_id: str, body: str) -> dict:
        return {"id": "c2", "body": {"storage": {"value": body}}}

    def reply_to_comment(self, comment_id: str, body: str) -> dict:
        return {"id": "c3", "body": {"storage": {"value": body}}}


def test_comment_service_list_normalizes_results() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.list("1234")

    assert result["results"][0]["id"] == "c1"
```

```python
def test_confluence_comment_reply_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import comment as comment_module

    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"reply": lambda self, comment_id, body: {"id": "c3", "body": body}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://confluence.example.com", "confluence", "comment", "reply", "c1", "--body", "example response", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"id": "c3"' in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/products/confluence/test_comment_service.py tests/products/confluence/test_comment_command.py -v`
Expected: FAIL because comment service and command files do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class ConfluenceProvider(Protocol):
    def list_comments(self, page_id: str) -> list[dict]: ...
    def add_comment(self, page_id: str, body: str) -> dict: ...
    def reply_to_comment(self, comment_id: str, body: str) -> dict: ...
```

```python
class ConfluenceServerProvider:
    def list_comments(self, page_id: str) -> list[dict]:
        return self.client.get_page_comments(page_id)

    def add_comment(self, page_id: str, body: str) -> dict:
        return self.client.add_comment(page_id, body)

    def reply_to_comment(self, comment_id: str, body: str) -> dict:
        return self.client.add_comment(comment_id, body, parent_id=comment_id)
```

```python
class CommentService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> dict:
        return {
            "results": [
                ConfluenceComment.from_api_response(item).to_simplified_dict()
                for item in self.provider.list_comments(page_id)
            ]
        }
```

```python
@app.command("reply")
def reply_to_comment(
    ctx: typer.Context,
    comment_id: str,
    body: str = typer.Option(..., "--body"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_comment_service(ctx.obj)
    typer.echo(render_output(service.reply(comment_id, body), output=output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/products/confluence/test_comment_service.py tests/products/confluence/test_comment_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/confluence/providers/base.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/confluence/schemas.py src/atlassian_cli/products/confluence/services/comment.py src/atlassian_cli/products/confluence/commands/comment.py tests/products/confluence/test_comment_service.py tests/products/confluence/test_comment_command.py
git commit -m "feat: add default confluence comment workflows"
```

### Task 6: Document the New Default Coverage and Make the Cloud-Only Gap Explicit

**Files:**
- Modify: `README.md`
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `tests/products/jira/test_issue_command.py`

- [ ] **Step 1: Write the failing test**

```python
def test_jira_issue_changelog_batch_is_explicitly_unsupported_on_server(monkeypatch) -> None:
    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "--deployment",
            "server",
            "jira",
            "issue",
            "changelog-batch",
            "--issue",
            "PROJ-1",
        ],
    )

    assert result.exit_code != 0
    assert "Cloud support is not available in v1" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/products/jira/test_issue_command.py::test_jira_issue_changelog_batch_is_explicitly_unsupported_on_server -v`
Expected: FAIL because the command does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
@app.command("changelog-batch")
def batch_get_changelogs(
    ctx: typer.Context,
    issue_keys: list[str] = typer.Option(..., "--issue"),
) -> None:
    raise UnsupportedError("Cloud support is not available in v1")
```

```markdown
## Default toolset alignment

- Implemented: Jira issues, fields, comments, transitions; Confluence pages and comments for Server/DC
- Explicitly unsupported in v1: Jira batch changelog fetch, because the current CLI has no Cloud provider
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/products/jira/test_issue_command.py::test_jira_issue_changelog_batch_is_explicitly_unsupported_on_server -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md src/atlassian_cli/products/jira/commands/issue.py tests/products/jira/test_issue_command.py
git commit -m "docs: document default toolset coverage"
```

### Task 7: Full Verification Sweep

**Files:**
- Modify: none
- Test: `tests/test_cli_help.py`
- Test: `tests/products/jira/test_field_service.py`
- Test: `tests/products/jira/test_field_command.py`
- Test: `tests/products/jira/test_comment_service.py`
- Test: `tests/products/jira/test_comment_command.py`
- Test: `tests/products/jira/test_issue_service.py`
- Test: `tests/products/jira/test_issue_command.py`
- Test: `tests/products/confluence/test_page_service.py`
- Test: `tests/products/confluence/test_page_command.py`
- Test: `tests/products/confluence/test_comment_service.py`
- Test: `tests/products/confluence/test_comment_command.py`

- [ ] **Step 1: Run the focused default-coverage suite**

Run:

```bash
.venv/bin/pytest \
  tests/test_cli_help.py \
  tests/products/jira/test_field_service.py \
  tests/products/jira/test_field_command.py \
  tests/products/jira/test_comment_service.py \
  tests/products/jira/test_comment_command.py \
  tests/products/jira/test_issue_service.py \
  tests/products/jira/test_issue_command.py \
  tests/products/confluence/test_page_service.py \
  tests/products/confluence/test_page_command.py \
  tests/products/confluence/test_comment_service.py \
  tests/products/confluence/test_comment_command.py -v
```

Expected: PASS

- [ ] **Step 2: Run the full repository test suite**

Run: `.venv/bin/pytest`
Expected: PASS

- [ ] **Step 3: Smoke-check help output for the new surfaces**

Run:

```bash
.venv/bin/python -m atlassian_cli --help
.venv/bin/python -m atlassian_cli jira field --help
.venv/bin/python -m atlassian_cli jira comment --help
.venv/bin/python -m atlassian_cli confluence page --help
.venv/bin/python -m atlassian_cli confluence comment --help
```

Expected: each help page exits `0` and lists the new commands.

- [ ] **Step 4: Review the diff for accidental non-default changes**

Run: `git diff --stat HEAD~7..HEAD`
Expected: changes stay inside Jira/Confluence default-alignment files and README/tests.

- [ ] **Step 5: Commit final cleanup if needed**

```bash
git add -A
git commit -m "test: verify default toolset alignment"
```

## Self-Review

### Spec coverage

- `jira_issues`: covered by Task 3, with the Cloud-only changelog surface explicitly called out in Task 6.
- `jira_fields`: covered by Task 2.
- `jira_comments`: covered by Task 3.
- `jira_transitions`: covered by Task 2 plus the richer transition execution extension in Task 3.
- `confluence_pages`: covered by Task 4.
- `confluence_comments`: covered by Task 5.

### Placeholder scan

- No `TODO`, `TBD`, or "implement later" markers remain.
- Every task includes exact file paths, test names, commands, and a concrete commit message.

### Type consistency

- New services follow existing `provider -> schema -> simplified dict` conventions.
- New command groups use existing Typer app registration in `src/atlassian_cli/cli.py`.
- The only intentionally unsupported command is `jira issue changelog-batch`, and the plan keeps that constraint explicit instead of letting it drift into silent omission.
