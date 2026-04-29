# Atlassian CLI Markdown-Default And Interactive Lists Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `table` output, make `markdown` the default human-readable mode, and ship phase-1 interactive browsing for representative collection commands with safe non-TTY fallback.

**Architecture:** Replace the current table-centric renderer with a markdown-centric output layer plus a small TTY/interactive dispatch seam. Keep machine-readable modes deterministic, add a lightweight prompt-toolkit-backed collection browser with a testable state core, and wire it first into `jira issue search` and `bitbucket pr list` while preserving full normalized `json` and `yaml` contracts.

**Tech Stack:** Python 3.13, Typer, Rich, prompt_toolkit, Pydantic v2, pytest

---

## Planned File Structure

### Create

- `src/atlassian_cli/output/markdown.py`
- `src/atlassian_cli/output/tty.py`
- `src/atlassian_cli/output/interactive.py`
- `tests/output/test_modes.py`
- `tests/output/test_markdown.py`
- `tests/output/test_tty.py`
- `tests/output/test_interactive.py`

### Modify

- `pyproject.toml`
- `src/atlassian_cli/cli.py`
- `src/atlassian_cli/config/models.py`
- `src/atlassian_cli/output/modes.py`
- `src/atlassian_cli/output/renderers.py`
- `src/atlassian_cli/products/jira/commands/issue.py`
- `src/atlassian_cli/products/jira/services/issue.py`
- `src/atlassian_cli/products/bitbucket/commands/pr.py`
- `src/atlassian_cli/products/bitbucket/services/pr.py`
- `src/atlassian_cli/products/bitbucket/providers/base.py`
- `src/atlassian_cli/products/bitbucket/providers/server.py`
- `tests/output/test_renderers.py`
- `tests/test_cli_help.py`
- `tests/test_cli_context.py`
- `tests/test_readme.py`
- `tests/integration/test_smoke.py`
- `tests/products/bitbucket/test_pr_command.py`
- `tests/products/bitbucket/test_pr_service.py`
- `tests/products/bitbucket/test_provider.py`
- `tests/products/jira/test_issue_command.py`
- `tests/products/jira/test_issue_service.py`
- `tests/products/test_factory.py`
- `README.md`

### Responsibility Notes

- `src/atlassian_cli/output/modes.py` should become the single source of truth for supported output values and human-vs-machine mode checks.
- `src/atlassian_cli/output/markdown.py` should own stable markdown rendering for both collection summaries and single-resource detail views.
- `src/atlassian_cli/output/tty.py` should own TTY detection and the policy for when interactive behavior is allowed.
- `src/atlassian_cli/output/interactive.py` should own collection-browser state, paging orchestration, and the prompt_toolkit runtime wrapper.
- Product command modules should decide whether they are serving a collection or a single-resource operation and route to markdown, machine serialization, or interactive browsing accordingly.
- Product service modules should keep normalized machine output explicit and add page/detail helpers where needed for the interactive browser.
- `bitbucket pr list` must gain explicit `start` and `limit` handling because phase 1 uses it as a representative interactive collection command.

### Common Commands

- Output tests: `.venv/bin/python -m pytest tests/output -v`
- Jira issue tests: `.venv/bin/python -m pytest tests/products/jira/test_issue_command.py tests/products/jira/test_issue_service.py -v`
- Bitbucket PR tests: `.venv/bin/python -m pytest tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_provider.py -v`
- CLI/docs contract tests: `.venv/bin/python -m pytest tests/test_cli_help.py tests/test_cli_context.py tests/test_readme.py tests/integration/test_smoke.py tests/products/test_factory.py -v`
- Full suite: `.venv/bin/python -m pytest -q`

## Task 1: Replace The Output Contract And Defaults

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `src/atlassian_cli/config/models.py`
- Modify: `src/atlassian_cli/output/modes.py`
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `src/atlassian_cli/products/jira/commands/project.py`
- Modify: `src/atlassian_cli/products/jira/commands/user.py`
- Modify: `src/atlassian_cli/products/confluence/commands/page.py`
- Modify: `src/atlassian_cli/products/confluence/commands/space.py`
- Modify: `src/atlassian_cli/products/confluence/commands/attachment.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/project.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/repo.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/branch.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Modify: `tests/integration/test_smoke.py`
- Modify: `tests/products/test_factory.py`
- Modify: `tests/test_cli_help.py`
- Create: `tests/output/test_modes.py`
- Test: `tests/output/test_modes.py`
- Test: `tests/test_cli_help.py`
- Test: `tests/products/test_factory.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/output/test_modes.py`:

```python
from atlassian_cli.output.modes import OutputMode, is_machine_output, is_raw_output, normalized_output


def test_normalized_output_preserves_markdown() -> None:
    assert normalized_output(OutputMode.MARKDOWN) == "markdown"
    assert normalized_output(OutputMode.RAW_JSON) == "json"
    assert normalized_output(OutputMode.RAW_YAML) == "yaml"


def test_machine_output_detection_excludes_markdown() -> None:
    assert is_machine_output(OutputMode.JSON) is True
    assert is_machine_output(OutputMode.YAML) is True
    assert is_machine_output(OutputMode.MARKDOWN) is False
    assert is_raw_output(OutputMode.RAW_JSON) is True
```

Append these tests to `tests/test_cli_help.py`:

```python
def test_nested_command_help_lists_markdown_output_mode() -> None:
    result = runner.invoke(app, ["jira", "issue", "get", "--help"])

    assert result.exit_code == 0
    assert "markdown" in result.stdout
    assert "table" not in result.stdout


def test_cli_rejects_removed_table_output_mode() -> None:
    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "get", "DEMO-1", "--output", "table"],
    )

    assert result.exit_code != 0
    assert "table" in result.stdout
```

Update the defaults in `tests/products/test_factory.py`:

```python
    context = ExecutionContext(
        profile="prod-jira",
        product=Product.JIRA,
        deployment=Deployment.SERVER,
        url="https://jira.example.com",
        output="markdown",
        auth=ResolvedAuth(mode=AuthMode.BASIC, username="example-user", token="secret"),
    )
```

```python
    context = ExecutionContext(
        profile="cloud-jira",
        product=Product.JIRA,
        deployment=Deployment.CLOUD,
        url="https://example.atlassian.net",
        output="markdown",
        auth=ResolvedAuth(mode=AuthMode.BASIC, username="example-user", token="secret"),
    )
```

Update the smoke-mode allow-list in `tests/integration/test_smoke.py`:

```python
    assert os.getenv("ATLASSIAN_OUTPUT", "json") in {
        "markdown",
        "json",
        "yaml",
        "raw-json",
        "raw-yaml",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/output/test_modes.py tests/test_cli_help.py tests/products/test_factory.py tests/integration/test_smoke.py -v`

Expected: FAIL because `OutputMode` and `is_machine_output()` do not exist yet, help still advertises `table`, `table` is still accepted, and the default output values in code still point to `table`.

- [ ] **Step 3: Write the minimal implementation**

Update `pyproject.toml` dependencies:

```toml
dependencies = [
  "atlassian-python-api>=4.0.7",
  "prompt_toolkit>=3.0.51",
  "pydantic>=2.12.0",
  "PyYAML>=6.0.2",
  "rich>=14.0.0",
  "typer>=0.16.0",
]
```

Replace `src/atlassian_cli/output/modes.py` with:

```python
from enum import StrEnum


class OutputMode(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    RAW_JSON = "raw-json"
    RAW_YAML = "raw-yaml"


def is_raw_output(output: str) -> bool:
    return output in {OutputMode.RAW_JSON, OutputMode.RAW_YAML}


def normalized_output(output: str) -> str:
    if output == OutputMode.RAW_JSON:
        return OutputMode.JSON
    if output == OutputMode.RAW_YAML:
        return OutputMode.YAML
    return output


def is_machine_output(output: str) -> bool:
    return normalized_output(output) in {OutputMode.JSON, OutputMode.YAML}
```

Update the root callback in `src/atlassian_cli/cli.py`:

```python
from atlassian_cli.output.modes import OutputMode


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
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    ...
                    output=output,
```

Update `src/atlassian_cli/config/models.py`:

```python
from atlassian_cli.output.modes import OutputMode


class RuntimeOverrides(BaseModel):
    ...
    output: str = Field(default=OutputMode.MARKDOWN)
```

Apply the same command-signature change to every command module listed in this task:

```python
from atlassian_cli.output.modes import OutputMode, is_raw_output


def get_issue(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/output/test_modes.py tests/test_cli_help.py tests/products/test_factory.py tests/integration/test_smoke.py -v`

Expected: PASS with `markdown` recognized, `table` rejected, and command help showing `markdown|json|yaml|raw-json|raw-yaml`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/atlassian_cli/cli.py src/atlassian_cli/config/models.py src/atlassian_cli/output/modes.py src/atlassian_cli/products/jira/commands/issue.py src/atlassian_cli/products/jira/commands/project.py src/atlassian_cli/products/jira/commands/user.py src/atlassian_cli/products/confluence/commands/page.py src/atlassian_cli/products/confluence/commands/space.py src/atlassian_cli/products/confluence/commands/attachment.py src/atlassian_cli/products/bitbucket/commands/project.py src/atlassian_cli/products/bitbucket/commands/repo.py src/atlassian_cli/products/bitbucket/commands/branch.py src/atlassian_cli/products/bitbucket/commands/pr.py tests/output/test_modes.py tests/test_cli_help.py tests/products/test_factory.py tests/integration/test_smoke.py
git commit -m "feat: replace table output contract"
```

## Task 2: Add Stable Markdown Rendering

**Files:**
- Create: `src/atlassian_cli/output/markdown.py`
- Modify: `src/atlassian_cli/output/renderers.py`
- Modify: `tests/output/test_renderers.py`
- Create: `tests/output/test_markdown.py`
- Test: `tests/output/test_markdown.py`
- Test: `tests/output/test_renderers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/output/test_markdown.py`:

```python
from atlassian_cli.output.markdown import render_markdown


def test_render_markdown_formats_single_resource_detail() -> None:
    payload = {
        "key": "DEMO-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "description": "Investigate the release pipeline",
    }

    rendered = render_markdown(payload)

    assert rendered.startswith("# DEMO-1 - Example issue summary")
    assert "- Status: Open" in rendered
    assert "## Description" in rendered
    assert "Investigate the release pipeline" in rendered


def test_render_markdown_formats_results_envelope_as_numbered_summary() -> None:
    payload = {
        "results": [
            {
                "id": 42,
                "title": "Example pull request",
                "state": "OPEN",
                "author": {"display_name": "Example Author"},
                "reviewers": ["reviewer-one", "reviewer-two", "reviewer-three", "reviewer-four"],
            }
        ]
    }

    rendered = render_markdown(payload)

    assert "1. 42 - Example pull request" in rendered
    assert "- State: OPEN" in rendered
    assert "- Author: Example Author" in rendered
    assert "- Reviewers: reviewer-one, reviewer-two, reviewer-three, +1 more" in rendered
```

Replace the table-specific assertions in `tests/output/test_renderers.py` with:

```python
def test_render_output_markdown_dispatches_to_markdown_renderer() -> None:
    payload = {"key": "DEMO-1", "summary": "Example issue summary"}

    rendered = render_output(payload, output="markdown")

    assert rendered.startswith("# DEMO-1 - Example issue summary")


def test_render_output_markdown_returns_empty_string_for_empty_lists() -> None:
    assert render_output([], output="markdown") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/output/test_markdown.py tests/output/test_renderers.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'atlassian_cli.output.markdown'` and failing markdown dispatch assertions because `render_output()` still tries to render tables.

- [ ] **Step 3: Write the minimal implementation**

Create `src/atlassian_cli/output/markdown.py`:

```python
from collections.abc import Mapping, Sequence
from typing import Any


MAX_SUMMARY_LIST_ITEMS = 3
DETAIL_BODY_FIELDS = {"description", "content"}


def _collection_items(value: Any) -> list[dict]:
    if isinstance(value, dict):
        for key in ("results", "issues"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _inline_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        for field in ("display_name", "display_id", "name", "title", "key", "id"):
            candidate = value.get(field)
            if candidate not in (None, ""):
                return str(candidate)
        return ""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = [_inline_value(item) for item in value]
        values = [item for item in values if item]
        if len(values) > MAX_SUMMARY_LIST_ITEMS:
            hidden = len(values) - MAX_SUMMARY_LIST_ITEMS
            values = [*values[:MAX_SUMMARY_LIST_ITEMS], f"+{hidden} more"]
        return ", ".join(values)
    return " ".join(str(value).split())


def _heading(record: Mapping[str, Any]) -> str:
    identifier = next(
        (str(record[field]) for field in ("key", "id", "slug", "name") if record.get(field) not in (None, "")),
        "Item",
    )
    title = next(
        (str(record[field]) for field in ("summary", "title", "name") if record.get(field) not in (None, "")),
        "",
    )
    return f"{identifier} - {title}" if title and title != identifier else identifier


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

    lines = [f"# {_heading(value)}"]
    for field, label in (
        ("state", "State"),
        ("status", "Status"),
        ("author", "Author"),
        ("assignee", "Assignee"),
        ("reporter", "Reporter"),
        ("from_ref", "From"),
        ("to_ref", "To"),
        ("created", "Created"),
        ("created_date", "Created"),
        ("updated", "Updated"),
        ("updated_date", "Updated"),
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

Replace `src/atlassian_cli/output/renderers.py` with:

```python
from atlassian_cli.output.formatters import to_json, to_yaml
from atlassian_cli.output.markdown import render_markdown
from atlassian_cli.output.modes import normalized_output


def render_output(value, *, output: str) -> str:
    output = normalized_output(output)
    if output == "markdown":
        return render_markdown(value)
    if output == "json":
        return to_json(value)
    if output == "yaml":
        return to_yaml(value)
    raise ValueError(f"unsupported output mode: {output}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/output/test_markdown.py tests/output/test_renderers.py -v`

Expected: PASS with markdown summary/detail rendering replacing the old table behavior and raw serializer tests still green.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/output/markdown.py src/atlassian_cli/output/renderers.py tests/output/test_markdown.py tests/output/test_renderers.py
git commit -m "feat: add markdown output renderer"
```

## Task 3: Add TTY Policy And Interactive Browser Core

**Files:**
- Create: `src/atlassian_cli/output/tty.py`
- Create: `src/atlassian_cli/output/interactive.py`
- Create: `tests/output/test_tty.py`
- Create: `tests/output/test_interactive.py`
- Test: `tests/output/test_tty.py`
- Test: `tests/output/test_interactive.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/output/test_tty.py`:

```python
from atlassian_cli.output.tty import should_use_interactive_output


def test_should_use_interactive_output_requires_markdown_collection_and_tty() -> None:
    assert should_use_interactive_output(
        "markdown",
        command_kind="collection",
        stdin_isatty=lambda: True,
        stdout_isatty=lambda: True,
    ) is True
    assert should_use_interactive_output(
        "json",
        command_kind="collection",
        stdin_isatty=lambda: True,
        stdout_isatty=lambda: True,
    ) is False
    assert should_use_interactive_output(
        "markdown",
        command_kind="detail",
        stdin_isatty=lambda: True,
        stdout_isatty=lambda: True,
    ) is False
    assert should_use_interactive_output(
        "markdown",
        command_kind="collection",
        stdin_isatty=lambda: False,
        stdout_isatty=lambda: True,
    ) is False
```

Create `tests/output/test_interactive.py`:

```python
from atlassian_cli.output.interactive import CollectionBrowserState, CollectionPage, InteractiveCollectionSource


def test_collection_browser_state_loads_next_page_when_advancing_past_loaded_items() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_page(start: int, limit: int) -> CollectionPage:
        calls.append((start, limit))
        return CollectionPage(
            items=[{"id": start + 1, "title": f"Item {start + 1}"}, {"id": start + 2, "title": f"Item {start + 2}"}],
            start=start,
            limit=limit,
            total=4,
        )

    source = InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=fetch_page,
        fetch_detail=lambda item: {"id": item["id"], "title": item["title"], "description": "Detail"},
        render_item=lambda index, item: f"{index}. {item['title']}",
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.move(1)
    state.move(1)

    assert calls == [(0, 2), (2, 2)]
    assert state.selected_index == 2


def test_collection_browser_state_opens_detail_and_returns_to_list() -> None:
    source = InteractiveCollectionSource(
        title="Demo",
        page_size=1,
        fetch_page=lambda start, limit: CollectionPage(
            items=[{"id": 1, "title": "DEMO-1"}],
            start=start,
            limit=limit,
            total=1,
        ),
        fetch_detail=lambda item: {"id": item["id"], "title": item["title"], "description": "Example issue summary"},
        render_item=lambda index, item: f"{index}. {item['title']}",
        render_detail=lambda item: item["description"],
    )
    state = CollectionBrowserState(source)

    state.load_initial()
    state.open_selected_detail()
    assert state.mode == "detail"
    assert state.detail_text == "Example issue summary"

    state.close_detail()
    assert state.mode == "list"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/output/test_tty.py tests/output/test_interactive.py -v`

Expected: FAIL with `ModuleNotFoundError` for the new `tty` and `interactive` modules.

- [ ] **Step 3: Write the minimal implementation**

Create `src/atlassian_cli/output/tty.py`:

```python
import sys

from atlassian_cli.output.modes import is_machine_output


def should_use_interactive_output(
    output: str,
    *,
    command_kind: str,
    stdin_isatty=None,
    stdout_isatty=None,
) -> bool:
    stdin_isatty = stdin_isatty or sys.stdin.isatty
    stdout_isatty = stdout_isatty or sys.stdout.isatty
    return (
        output == "markdown"
        and command_kind == "collection"
        and stdin_isatty()
        and stdout_isatty()
        and not is_machine_output(output)
    )
```

Create `src/atlassian_cli/output/interactive.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Callable

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl


@dataclass
class CollectionPage:
    items: list[dict[str, Any]]
    start: int
    limit: int
    total: int | None = None


@dataclass
class InteractiveCollectionSource:
    title: str
    page_size: int
    fetch_page: Callable[[int, int], CollectionPage]
    fetch_detail: Callable[[dict[str, Any]], dict[str, Any]]
    render_item: Callable[[int, dict[str, Any]], str]
    render_detail: Callable[[dict[str, Any]], str]


@dataclass
class CollectionBrowserState:
    source: InteractiveCollectionSource
    items: list[dict[str, Any]] = field(default_factory=list)
    selected_index: int = 0
    mode: str = "list"
    detail_text: str = ""
    next_start: int = 0
    total: int | None = None

    def load_initial(self) -> None:
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self.next_start = page.start + page.limit
        self.total = page.total

    def move(self, delta: int) -> None:
        target = self.selected_index + delta
        if target >= len(self.items) and self.total is not None and len(self.items) < self.total:
            page = self.source.fetch_page(self.next_start, self.source.page_size)
            self.items.extend(page.items)
            self.next_start = page.start + page.limit
            self.total = page.total
        self.selected_index = max(0, min(target, len(self.items) - 1))

    def open_selected_detail(self) -> None:
        detail = self.source.fetch_detail(self.items[self.selected_index])
        self.detail_text = self.source.render_detail(detail)
        self.mode = "detail"

    def close_detail(self) -> None:
        self.mode = "list"


def browse_collection(source: InteractiveCollectionSource) -> None:
    state = CollectionBrowserState(source)
    state.load_initial()
    body = FormattedTextControl(text=lambda: _render_state(state))
    bindings = KeyBindings()

    @bindings.add("q")
    def _quit(event) -> None:
        event.app.exit()

    @bindings.add("down")
    @bindings.add("j")
    def _down(event) -> None:
        if state.mode == "list":
            state.move(1)

    @bindings.add("up")
    @bindings.add("k")
    def _up(event) -> None:
        if state.mode == "list":
            state.move(-1)

    @bindings.add("enter")
    def _open(event) -> None:
        if state.mode == "list":
            state.open_selected_detail()

    @bindings.add("escape")
    @bindings.add("b")
    def _back(event) -> None:
        if state.mode == "detail":
            state.close_detail()

    app = Application(
        layout=Layout(HSplit([Window(content=body)])),
        key_bindings=bindings,
        full_screen=False,
    )
    app.run()


def _render_state(state: CollectionBrowserState) -> str:
    if state.mode == "detail":
        return state.detail_text
    lines = [state.source.title, ""]
    for index, item in enumerate(state.items):
        prefix = "> " if index == state.selected_index else "  "
        lines.append(prefix + state.source.render_item(index + 1, item))
    lines.extend(["", "j/k or arrows: move  enter: detail  b/esc: back  q: quit"])
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/output/test_tty.py tests/output/test_interactive.py -v`

Expected: PASS with TTY gating logic and browser state paging/detail behavior covered without needing a real terminal.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/output/tty.py src/atlassian_cli/output/interactive.py tests/output/test_tty.py tests/output/test_interactive.py
git commit -m "feat: add interactive collection browser scaffolding"
```

## Task 4: Wire Phase-1 Interactive Collection Commands

**Files:**
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `src/atlassian_cli/products/jira/services/issue.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/pr.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Modify: `tests/products/jira/test_issue_command.py`
- Modify: `tests/products/jira/test_issue_service.py`
- Modify: `tests/products/bitbucket/test_pr_command.py`
- Modify: `tests/products/bitbucket/test_pr_service.py`
- Modify: `tests/products/bitbucket/test_provider.py`
- Test: `tests/products/jira/test_issue_command.py`
- Test: `tests/products/jira/test_issue_service.py`
- Test: `tests/products/bitbucket/test_pr_command.py`
- Test: `tests/products/bitbucket/test_pr_service.py`
- Test: `tests/products/bitbucket/test_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/products/jira/test_issue_command.py`:

```python
from atlassian_cli.output.interactive import CollectionPage


def test_jira_issue_search_uses_interactive_browser_for_markdown_tty(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(issue_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(issue_module, "browse_collection", lambda source: calls.setdefault("source", source))
    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "search": lambda self, jql, start, limit: {
                    "issues": [{"key": "DEMO-1", "summary": "Example issue summary"}],
                    "start_at": start,
                    "max_results": limit,
                    "total": 1,
                },
                "search_page": lambda self, jql, start, limit: CollectionPage(
                    items=[{"key": "DEMO-1", "summary": "Example issue summary"}],
                    start=start,
                    limit=limit,
                    total=1,
                ),
                "get": lambda self, issue_key: {"key": issue_key, "summary": "Example issue summary"},
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = DEMO"],
    )

    assert result.exit_code == 0
    assert calls["source"].title == "Jira issue search"


def test_jira_issue_search_non_tty_falls_back_to_markdown(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(issue_module, "should_use_interactive_output", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "search": lambda self, jql, start, limit: {
                    "issues": [{"key": "DEMO-1", "summary": "Example issue summary"}],
                    "start_at": start,
                    "max_results": limit,
                    "total": 1,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = DEMO"],
    )

    assert result.exit_code == 0
    assert "1. DEMO-1 - Example issue summary" in result.stdout
```

Append to `tests/products/bitbucket/test_provider.py`:

```python
def test_list_pull_requests_materializes_paged_generator_with_start_and_limit() -> None:
    calls = {}

    class FakeClient:
        def get_pull_requests(self, project_key: str, repo_slug: str, state: str, limit: int, start: int):
            calls["args"] = (project_key, repo_slug, state, limit, start)
            yield {"id": 1, "title": "Add release automation"}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_pull_requests("DEMO", "example-repo", "OPEN", start=25, limit=10)

    assert result == [{"id": 1, "title": "Add release automation"}]
    assert calls["args"] == ("DEMO", "example-repo", "OPEN", 10, 25)
```

Update the existing fake provider in `tests/products/bitbucket/test_pr_service.py`:

```python
    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> list[dict]:
        assert start >= 0
        assert limit > 0
        return [
            {
                "id": 42,
                "title": "Example pull request",
                "state": "OPEN",
                "version": 7,
                "reviewers": [{"user": {"displayName": "reviewer-one"}, "approved": True}],
                "fromRef": {"displayId": "feature/DEMO-1234/example-change"},
                "toRef": {"displayId": "main"},
            }
        ]
```

Append to `tests/products/bitbucket/test_pr_service.py`:

```python
def test_pull_request_service_list_accepts_start_and_limit() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.list("DEMO", "example-skills", "OPEN", start=25, limit=10)

    assert result["results"][0]["id"] == 42
```

Append to `tests/products/bitbucket/test_pr_command.py`:

```python
from atlassian_cli.output.interactive import CollectionPage


def test_bitbucket_pr_list_uses_interactive_browser_for_markdown_tty(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(pr_module, "browse_collection", lambda source: calls.setdefault("source", source))
    monkeypatch.setattr(
        pr_module,
        "build_pr_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, project_key, repo_slug, state, start, limit: {
                    "results": [{"id": 42, "title": "Example pull request"}],
                    "start_at": start,
                    "max_results": limit,
                },
                "list_page": lambda self, project_key, repo_slug, state, start, limit: CollectionPage(
                    items=[{"id": 42, "title": "Example pull request"}],
                    start=start,
                    limit=limit,
                    total=1,
                ),
                "get": lambda self, project_key, repo_slug, pr_id: {"id": pr_id, "title": "Example pull request"},
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "list", "DEMO", "example-repo"],
    )

    assert result.exit_code == 0
    assert calls["source"].title == "Bitbucket pull requests"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/products/jira/test_issue_command.py tests/products/jira/test_issue_service.py tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_provider.py -v`

Expected: FAIL because the commands do not yet branch into the interactive browser, `bitbucket pr list` does not accept `start`/`limit`, and the Bitbucket provider signature does not forward paging arguments.

- [ ] **Step 3: Write the minimal implementation**

Update `src/atlassian_cli/products/jira/commands/issue.py`:

```python
from atlassian_cli.output.interactive import InteractiveCollectionSource, browse_collection
from atlassian_cli.output.markdown import render_markdown
from atlassian_cli.output.tty import should_use_interactive_output


@app.command("search")
def search_issues(
    ctx: typer.Context,
    jql: str = typer.Option(..., "--jql"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_issue_service(ctx.obj)
    if is_raw_output(output):
        payload = service.search_raw(jql=jql, start=start, limit=limit)
        typer.echo(render_output(payload, output=output))
        return

    if should_use_interactive_output(output, command_kind="collection"):
        browse_collection(
            InteractiveCollectionSource(
                title="Jira issue search",
                page_size=limit,
                fetch_page=lambda page_start, page_limit: service.search_page(jql, page_start, page_limit),
                fetch_detail=lambda item: service.get(item["key"]),
                render_item=lambda index, item: render_markdown({"results": [item]}).splitlines()[0],
                render_detail=render_markdown,
            )
        )
        return

    typer.echo(render_output(service.search(jql=jql, start=start, limit=limit), output=output))
```

Update `src/atlassian_cli/products/jira/services/issue.py`:

```python
from atlassian_cli.output.interactive import CollectionPage


def search_page(self, jql: str, start: int, limit: int) -> CollectionPage:
    payload = self.search(jql, start, limit)
    return CollectionPage(
        items=payload["issues"],
        start=payload["start_at"],
        limit=payload["max_results"],
        total=payload["total"],
    )
```

Update `src/atlassian_cli/products/bitbucket/providers/base.py`:

```python
    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int,
        limit: int,
    ) -> list[dict]: ...
```

Update `src/atlassian_cli/products/bitbucket/providers/server.py`:

```python
    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_pull_requests(
                project_key,
                repo_slug,
                state=state,
                limit=limit,
                start=start,
            )
        )
```

Update `src/atlassian_cli/products/bitbucket/services/pr.py`:

```python
from atlassian_cli.output.interactive import CollectionPage


def list(self, project_key: str, repo_slug: str, state: str, start: int = 0, limit: int = 25) -> dict:
    prs = [
        BitbucketPullRequest.from_api_response(item).to_simplified_dict()
        for item in self.provider.list_pull_requests(
            project_key,
            repo_slug,
            state,
            start=start,
            limit=limit,
        )
    ]
    return {"results": prs, "start_at": start, "max_results": limit}


def list_raw(
    self,
    project_key: str,
    repo_slug: str,
    state: str,
    *,
    start: int = 0,
    limit: int = 25,
) -> list[dict]:
    return self.provider.list_pull_requests(
        project_key,
        repo_slug,
        state,
        start=start,
        limit=limit,
    )


def list_page(
    self,
    project_key: str,
    repo_slug: str,
    state: str,
    start: int,
    limit: int,
) -> CollectionPage:
    payload = self.list(project_key, repo_slug, state, start=start, limit=limit)
    return CollectionPage(items=payload["results"], start=start, limit=limit, total=None)
```

Update `src/atlassian_cli/products/bitbucket/commands/pr.py`:

```python
from atlassian_cli.output.interactive import InteractiveCollectionSource, browse_collection
from atlassian_cli.output.markdown import render_markdown
from atlassian_cli.output.tty import should_use_interactive_output


@app.command("list")
def list_pull_requests(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    state: str = typer.Option("OPEN", "--state"),
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(25, "--limit"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    if is_raw_output(output):
        typer.echo(render_output(service.list_raw(project_key, repo_slug, state, start=start, limit=limit), output=output))
        return

    if should_use_interactive_output(output, command_kind="collection"):
        browse_collection(
            InteractiveCollectionSource(
                title="Bitbucket pull requests",
                page_size=limit,
                fetch_page=lambda page_start, page_limit: service.list_page(project_key, repo_slug, state, page_start, page_limit),
                fetch_detail=lambda item: service.get(project_key, repo_slug, item["id"]),
                render_item=lambda index, item: render_markdown({"results": [item]}).splitlines()[0],
                render_detail=render_markdown,
            )
        )
        return

    typer.echo(render_output(service.list(project_key, repo_slug, state, start=start, limit=limit), output=output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/products/jira/test_issue_command.py tests/products/jira/test_issue_service.py tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_provider.py -v`

Expected: PASS with interactive dispatch covered by monkeypatch-based command tests, `jira issue search` paging exposed through `CollectionPage`, and `bitbucket pr list` forwarding `start`/`limit`.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/jira/commands/issue.py src/atlassian_cli/products/jira/services/issue.py src/atlassian_cli/products/bitbucket/commands/pr.py src/atlassian_cli/products/bitbucket/services/pr.py src/atlassian_cli/products/bitbucket/providers/base.py src/atlassian_cli/products/bitbucket/providers/server.py tests/products/jira/test_issue_command.py tests/products/jira/test_issue_service.py tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_pr_service.py tests/products/bitbucket/test_provider.py
git commit -m "feat: add phase-one interactive collection commands"
```

## Task 5: Update README, Help, And Docs Contract Tests

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Modify: `tests/test_cli_help.py`
- Test: `tests/test_readme.py`
- Test: `tests/test_cli_help.py`

- [ ] **Step 1: Write the failing tests**

Update `tests/test_readme.py`:

```python
def test_readme_mentions_markdown_default_and_interactive_lists() -> None:
    readme = Path("README.md").read_text()

    assert "markdown" in readme
    assert "interactive" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
    assert "table" not in readme
```

Append to `tests/test_cli_help.py`:

```python
def test_pr_list_help_mentions_markdown_output_mode() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--help"])

    assert result.exit_code == 0
    assert "markdown" in result.stdout
    assert "table" not in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_readme.py tests/test_cli_help.py -v`

Expected: FAIL because the README still describes the old output model and examples do not mention markdown-default or interactive collection behavior.

- [ ] **Step 3: Write the minimal implementation**

Update the `README.md` output section to this structure:

```md
## Output Modes

The CLI now uses `markdown` as the default human-readable mode.

- Single-resource commands default to markdown detail output.
- Collection commands default to an interactive browser in a TTY.
- Collection commands fall back to markdown summary output outside a TTY.
- Use `--output json` or `--output yaml` for normalized machine-readable output.
- Use `--output raw-json` or `--output raw-yaml` for the original provider response.
```

Add examples:

```md
- `atlassian jira issue get DEMO-1`
- `atlassian jira issue search --jql 'project = DEMO'`
- `atlassian bitbucket pr list DEMO example-repo`
- `atlassian bitbucket pr list DEMO example-repo --output json`
```

Remove any remaining `table` references from `README.md`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_readme.py tests/test_cli_help.py -v`

Expected: PASS with README and help output aligned to the new output contract and no lingering `table` references.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py tests/test_cli_help.py
git commit -m "docs: describe markdown output and interactive lists"
```
