# Atlassian CLI Interactive Browser Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the phase-one interactive collection browser into a dense list-plus-preview browser that is practical as the default TTY browsing experience, with Bitbucket pull requests getting a purpose-built compact row and preview.

**Architecture:** This plan is incremental on top of `docs/superpowers/plans/2026-04-28-atlassian-cli-markdown-default-interactive-lists-phase-1.md`. Extend the generic `src/atlassian_cli/output/interactive.py` browser state so list mode renders a compact list block, a live preview block, and a footer block, while full detail still opens separately on `Enter`. Keep browser-layer truncation in `interactive.py`, add generic preview helpers in `output/markdown.py`, and add Bitbucket pull-request-specific compact renderers in a new product-local module so product formatting stays out of the generic browser runtime.

**Tech Stack:** Python 3.13, Typer, prompt_toolkit, Rich, Pydantic v2, pytest

---

## Prerequisite

This spec refines the browser introduced by `docs/superpowers/plans/2026-04-28-atlassian-cli-markdown-default-interactive-lists-phase-1.md`.

- Execute that plan first if these files do not already exist in the worktree:
  - `src/atlassian_cli/output/interactive.py`
  - `src/atlassian_cli/output/markdown.py`
  - `src/atlassian_cli/output/tty.py`
  - `tests/output/test_interactive.py`
- Do not duplicate the larger markdown-default migration work in this plan. This plan assumes the markdown output contract and initial interactive dispatch already exist.

## Planned File Structure

### Create

- `src/atlassian_cli/products/bitbucket/browser.py`
- `tests/products/bitbucket/test_browser.py`

### Modify

- `src/atlassian_cli/output/interactive.py`
- `src/atlassian_cli/output/markdown.py`
- `src/atlassian_cli/products/bitbucket/commands/pr.py`
- `src/atlassian_cli/products/jira/commands/issue.py`
- `tests/output/test_interactive.py`
- `tests/output/test_markdown.py`
- `tests/products/bitbucket/test_pr_command.py`
- `tests/products/jira/test_issue_command.py`
- `tests/test_readme.py`
- `README.md`

### Responsibility Notes

- `src/atlassian_cli/output/interactive.py` remains the generic browser runtime. It owns state, paging, filtering, refresh, keybindings, and width-bounded truncation. It must not know Bitbucket-specific field names.
- `src/atlassian_cli/output/markdown.py` owns generic fallback one-line item rendering and concise preview rendering for non-Bitbucket collection browsers.
- `src/atlassian_cli/products/bitbucket/browser.py` owns the compact `bitbucket pr list` row, reviewers summary, branch preview lines, timestamp presentation, and description excerpt logic.
- Product command modules only wire fetchers and renderer functions into `InteractiveCollectionSource`. They should not implement truncation rules inline.

### Common Commands

- Interactive core tests: `.venv/bin/python -m pytest tests/output/test_interactive.py -v`
- Markdown/browser formatting tests: `.venv/bin/python -m pytest tests/output/test_markdown.py tests/products/bitbucket/test_browser.py -v`
- Command wiring tests: `.venv/bin/python -m pytest tests/products/bitbucket/test_pr_command.py tests/products/jira/test_issue_command.py -v`
- Docs contract test: `.venv/bin/python -m pytest tests/test_readme.py -v`

## Task 1: Add The Stacked Preview Layout And Browser-Layer Truncation

**Files:**
- Modify: `src/atlassian_cli/output/interactive.py`
- Modify: `tests/output/test_interactive.py`
- Test: `tests/output/test_interactive.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/output/test_interactive.py`:

```python
from atlassian_cli.output.interactive import (
    CollectionBrowserState,
    CollectionPage,
    InteractiveCollectionSource,
    render_state,
)


def build_preview_source() -> InteractiveCollectionSource:
    items = [
        {
            "id": 24990,
            "state": "OPEN",
            "author": "sample-author",
            "title": "[FEAT] DEMO-1234 example preview change",
            "preview": "\n".join(
                [
                    "State: OPEN",
                    "Author: sample-author",
                    "Reviewers: Alice, Bob, Carol, +1 more",
                    "From: feature/DEMO-1234/example-change",
                    "To: main",
                    "Updated: 2026-04-27 13:19:55",
                    "",
                    "Description:",
                    "Example description for preview rendering.",
                ]
            ),
            "detail": "# PR #24990\n\nFull markdown detail",
        },
        {
            "id": 24991,
            "state": "MERGED",
            "author": "alice",
            "title": "Release cleanup",
            "preview": "State: MERGED\nAuthor: alice",
            "detail": "# PR #24991\n\nMerged detail",
        },
    ]

    return InteractiveCollectionSource(
        title="Bitbucket pull requests",
        page_size=2,
        fetch_page=lambda start, limit: CollectionPage(items=items[start : start + limit], start=start, limit=limit, total=len(items)),
        fetch_detail=lambda item: item,
        render_item=lambda index, item: f"{item['id']}  {item['state']}  {item['author']}  {item['title']}",
        render_preview=lambda item: item["preview"],
        render_detail=lambda item: item["detail"],
    )


def test_render_state_stacks_list_preview_and_footer() -> None:
    state = CollectionBrowserState(build_preview_source())
    state.load_initial()

    rendered = render_state(state, width=54, preview_lines=7)

    assert "Preview:" in rendered
    assert "j/k move  enter detail  b/esc back  q quit" in rendered
    selected_line = next(line for line in rendered.splitlines() if line.startswith("> "))
    assert selected_line.count("\n") == 0
    assert selected_line.endswith("...")


def test_collection_browser_state_updates_preview_when_selection_changes() -> None:
    state = CollectionBrowserState(build_preview_source())
    state.load_initial()

    assert "Author: sample-author" in render_state(state, width=80, preview_lines=7)

    state.move(1)

    rendered = render_state(state, width=80, preview_lines=7)
    assert "Author: alice" in rendered
    assert "Author: sample-author" not in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/output/test_interactive.py -v`

Expected: FAIL because `InteractiveCollectionSource` does not yet accept `render_preview`, `CollectionBrowserState` does not track preview text, and `render_state()` does not exist.

- [ ] **Step 3: Write the minimal implementation**

Replace `src/atlassian_cli/output/interactive.py` with:

```python
from dataclasses import dataclass, field
from typing import Any, Callable

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl


LIST_FOOTER = "j/k move  enter detail  b/esc back  q quit"


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
    render_preview: Callable[[dict[str, Any]], str]
    render_detail: Callable[[dict[str, Any]], str]


@dataclass
class CollectionBrowserState:
    source: InteractiveCollectionSource
    items: list[dict[str, Any]] = field(default_factory=list)
    selected_index: int = 0
    mode: str = "list"
    detail_text: str = ""
    preview_text: str = ""
    next_start: int = 0
    total: int | None = None

    def load_initial(self) -> None:
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self.selected_index = 0
        self.next_start = page.start + page.limit
        self.total = page.total
        self._sync_preview()

    def move(self, delta: int) -> None:
        target = self.selected_index + delta
        while target >= len(self.items) and self._can_load_more():
            self._load_next_page()
        self.selected_index = max(0, min(target, len(self.items) - 1))
        self._sync_preview()

    def open_selected_detail(self) -> None:
        if not self.items:
            return
        detail = self.source.fetch_detail(self.items[self.selected_index])
        self.detail_text = self.source.render_detail(detail)
        self.mode = "detail"

    def close_detail(self) -> None:
        self.mode = "list"
        self._sync_preview()

    def _can_load_more(self) -> bool:
        return self.total is None or len(self.items) < self.total

    def _load_next_page(self) -> None:
        page = self.source.fetch_page(self.next_start, self.source.page_size)
        self.items.extend(page.items)
        self.next_start = page.start + page.limit
        self.total = page.total

    def _sync_preview(self) -> None:
        if not self.items:
            self.preview_text = "No results."
            return
        self.preview_text = self.source.render_preview(self.items[self.selected_index])


def ellipsize(text: str, width: int) -> str:
    normalized = " ".join(text.split())
    if width <= 0:
        return ""
    if len(normalized) <= width:
        return normalized
    if width <= 3:
        return "." * width
    return normalized[: width - 3] + "..."


def clip_block(text: str, *, width: int, max_lines: int) -> str:
    lines = [ellipsize(line, width) for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    if len(lines) <= max_lines:
        return "\n".join(lines)
    clipped = lines[:max_lines]
    clipped[-1] = ellipsize(f"{clipped[-1]}...", width)
    return "\n".join(clipped)


def render_state(state: CollectionBrowserState, *, width: int, preview_lines: int = 8) -> str:
    if state.mode == "detail":
        return state.detail_text

    row_width = max(width - 2, 8)
    lines = [state.source.title, ""]
    for index, item in enumerate(state.items):
        prefix = "> " if index == state.selected_index else "  "
        lines.append(prefix + ellipsize(state.source.render_item(index + 1, item), row_width))

    preview = clip_block(state.preview_text, width=width, max_lines=preview_lines)
    lines.extend(["", "Preview:", preview, "", LIST_FOOTER])
    return "\n".join(lines).strip()


def browse_collection(source: InteractiveCollectionSource) -> None:
    state = CollectionBrowserState(source)
    state.load_initial()
    control = FormattedTextControl(
        text=lambda: render_state(
            state,
            width=max(get_app().output.get_size().columns - 1, 20),
        )
    )
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

    Application(
        layout=Layout(Window(content=control)),
        key_bindings=bindings,
        full_screen=False,
    ).run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/output/test_interactive.py -v`

Expected: PASS with selection-driven preview updates, one-line list rows, and browser-layer ellipsis handling covered by pure rendering tests.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/output/interactive.py tests/output/test_interactive.py
git commit -m "feat: add interactive browser preview layout"
```

## Task 2: Add Filtering, Refresh, And Page Navigation To The Browser State

**Files:**
- Modify: `src/atlassian_cli/output/interactive.py`
- Modify: `tests/output/test_interactive.py`
- Test: `tests/output/test_interactive.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/output/test_interactive.py`:

```python
def build_filter_source(calls: list[tuple[int, int]]) -> InteractiveCollectionSource:
    pages = {
        0: CollectionPage(
            items=[
                {"id": 1, "title": "Alpha", "preview": "State: OPEN", "detail": "# Alpha"},
                {"id": 2, "title": "Beta", "preview": "State: OPEN", "detail": "# Beta"},
            ],
            start=0,
            limit=2,
            total=4,
        ),
        2: CollectionPage(
            items=[
                {"id": 3, "title": "Gamma", "preview": "State: MERGED", "detail": "# Gamma"},
                {"id": 4, "title": "Delta", "preview": "State: DECLINED", "detail": "# Delta"},
            ],
            start=2,
            limit=2,
            total=4,
        ),
    }

    def fetch_page(start: int, limit: int) -> CollectionPage:
        calls.append((start, limit))
        return pages[start]

    return InteractiveCollectionSource(
        title="Demo",
        page_size=2,
        fetch_page=fetch_page,
        fetch_detail=lambda item: item,
        render_item=lambda index, item: item["title"],
        render_preview=lambda item: item["preview"],
        render_detail=lambda item: item["detail"],
        filter_text=lambda item: item["title"],
    )


def test_collection_browser_state_moves_by_page_size() -> None:
    calls: list[tuple[int, int]] = []
    state = CollectionBrowserState(build_filter_source(calls))
    state.load_initial()

    state.move_page(1)

    assert calls == [(0, 2), (2, 2)]
    assert state.visible_items[state.selected_index]["title"] == "Gamma"


def test_collection_browser_state_applies_local_filter_and_resets_selection() -> None:
    calls: list[tuple[int, int]] = []
    state = CollectionBrowserState(build_filter_source(calls))
    state.load_initial()
    state.move(1)

    state.begin_filter()
    state.append_filter("g")
    state.apply_filter()

    assert [item["title"] for item in state.visible_items] == ["Gamma"]
    assert state.selected_index == 0
    assert calls == [(0, 2)]


def test_collection_browser_state_refresh_returns_to_list_mode() -> None:
    calls: list[tuple[int, int]] = []
    state = CollectionBrowserState(build_filter_source(calls))
    state.load_initial()
    state.open_selected_detail()

    state.refresh()

    assert state.mode == "list"
    assert state.selected_index == 0
    assert calls == [(0, 2), (0, 2)]


def test_render_state_shows_filter_prompt() -> None:
    calls: list[tuple[int, int]] = []
    state = CollectionBrowserState(build_filter_source(calls))
    state.load_initial()
    state.begin_filter()
    state.append_filter("be")

    rendered = render_state(state, width=60, preview_lines=5)

    assert "Filter: be_" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/output/test_interactive.py -v`

Expected: FAIL because `InteractiveCollectionSource` does not expose `filter_text`, `CollectionBrowserState` has no `move_page()`, filter methods, or `refresh()`, and `render_state()` still renders the old footer.

- [ ] **Step 3: Write the minimal implementation**

Update `src/atlassian_cli/output/interactive.py` so `InteractiveCollectionSource`, `CollectionBrowserState`, `render_state()`, and `browse_collection()` match this shape:

```python
from prompt_toolkit.keys import Keys


LIST_FOOTER = "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit"


@dataclass
class InteractiveCollectionSource:
    title: str
    page_size: int
    fetch_page: Callable[[int, int], CollectionPage]
    fetch_detail: Callable[[dict[str, Any]], dict[str, Any]]
    render_item: Callable[[int, dict[str, Any]], str]
    render_preview: Callable[[dict[str, Any]], str]
    render_detail: Callable[[dict[str, Any]], str]
    filter_text: Callable[[dict[str, Any]], str] | None = None


@dataclass
class CollectionBrowserState:
    source: InteractiveCollectionSource
    items: list[dict[str, Any]] = field(default_factory=list)
    selected_index: int = 0
    mode: str = "list"
    detail_text: str = ""
    preview_text: str = ""
    next_start: int = 0
    total: int | None = None
    filter_query: str = ""
    filter_buffer: str = ""

    @property
    def visible_items(self) -> list[dict[str, Any]]:
        if not self.filter_query:
            return self.items
        needle = self.filter_query.lower()
        matcher = self.source.filter_text or _default_filter_text
        return [item for item in self.items if needle in matcher(item).lower()]

    def load_initial(self) -> None:
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self.selected_index = 0
        self.next_start = page.start + page.limit
        self.total = page.total
        self._sync_preview()

    def move(self, delta: int) -> None:
        target = self.selected_index + delta
        while not self.filter_query and target >= len(self.visible_items) and self._can_load_more():
            self._load_next_page()
        self.selected_index = _clamp(target, len(self.visible_items))
        self._sync_preview()

    def move_page(self, delta_pages: int) -> None:
        self.move(delta_pages * self.source.page_size)

    def begin_filter(self) -> None:
        self.mode = "filter"
        self.filter_buffer = self.filter_query

    def append_filter(self, text: str) -> None:
        self.filter_buffer += text

    def backspace_filter(self) -> None:
        self.filter_buffer = self.filter_buffer[:-1]

    def apply_filter(self) -> None:
        self.filter_query = self.filter_buffer.strip()
        self.selected_index = 0
        self.mode = "list"
        self._sync_preview()

    def cancel_filter(self) -> None:
        self.filter_buffer = ""
        self.mode = "list"
        self._sync_preview()

    def refresh(self) -> None:
        self.mode = "list"
        self.detail_text = ""
        page = self.source.fetch_page(0, self.source.page_size)
        self.items = list(page.items)
        self.selected_index = 0
        self.next_start = page.start + page.limit
        self.total = page.total
        self._sync_preview()

    def open_selected_detail(self) -> None:
        current = self.current_item
        if current is None:
            return
        detail = self.source.fetch_detail(current)
        self.detail_text = self.source.render_detail(detail)
        self.mode = "detail"

    def close_detail(self) -> None:
        self.mode = "list"
        self._sync_preview()

    @property
    def current_item(self) -> dict[str, Any] | None:
        if not self.visible_items:
            return None
        return self.visible_items[self.selected_index]

    def _can_load_more(self) -> bool:
        return self.total is None or len(self.items) < self.total

    def _load_next_page(self) -> None:
        page = self.source.fetch_page(self.next_start, self.source.page_size)
        self.items.extend(page.items)
        self.next_start = page.start + page.limit
        self.total = page.total

    def _sync_preview(self) -> None:
        current = self.current_item
        if current is None:
            self.preview_text = "No results."
            return
        self.preview_text = self.source.render_preview(current)


def _default_filter_text(item: dict[str, Any]) -> str:
    return " ".join(str(value) for value in item.values())


def _clamp(index: int, size: int) -> int:
    if size <= 0:
        return 0
    return max(0, min(index, size - 1))


def render_state(state: CollectionBrowserState, *, width: int, preview_lines: int = 8) -> str:
    if state.mode == "detail":
        return state.detail_text

    row_width = max(width - 2, 8)
    lines = [state.source.title, ""]
    for index, item in enumerate(state.visible_items):
        prefix = "> " if index == state.selected_index else "  "
        lines.append(prefix + ellipsize(state.source.render_item(index + 1, item), row_width))

    preview = clip_block(state.preview_text, width=width, max_lines=preview_lines)
    footer = f"Filter: {state.filter_buffer}_" if state.mode == "filter" else LIST_FOOTER
    lines.extend(["", "Preview:", preview, "", footer])
    return "\n".join(lines).strip()


def browse_collection(source: InteractiveCollectionSource) -> None:
    state = CollectionBrowserState(source)
    state.load_initial()
    control = FormattedTextControl(
        text=lambda: render_state(
            state,
            width=max(get_app().output.get_size().columns - 1, 20),
        )
    )
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

    @bindings.add("pagedown")
    @bindings.add("n")
    def _next_page(event) -> None:
        if state.mode == "list":
            state.move_page(1)

    @bindings.add("pageup")
    @bindings.add("p")
    def _previous_page(event) -> None:
        if state.mode == "list":
            state.move_page(-1)

    @bindings.add("/")
    def _start_filter(event) -> None:
        if state.mode == "list":
            state.begin_filter()

    @bindings.add("r")
    def _refresh(event) -> None:
        if state.mode in {"list", "detail"}:
            state.refresh()

    @bindings.add("backspace")
    def _backspace(event) -> None:
        if state.mode == "filter":
            state.backspace_filter()

    @bindings.add(Keys.Any)
    def _type_filter(event) -> None:
        if state.mode == "filter" and event.data and event.data.isprintable():
            state.append_filter(event.data)

    @bindings.add("enter")
    def _enter(event) -> None:
        if state.mode == "filter":
            state.apply_filter()
        elif state.mode == "list":
            state.open_selected_detail()

    @bindings.add("escape")
    def _escape(event) -> None:
        if state.mode == "filter":
            state.cancel_filter()
        elif state.mode == "detail":
            state.close_detail()

    @bindings.add("b")
    def _back(event) -> None:
        if state.mode == "detail":
            state.close_detail()

    Application(
        layout=Layout(Window(content=control)),
        key_bindings=bindings,
        full_screen=False,
    ).run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/output/test_interactive.py -v`

Expected: PASS with page-size jumps, local filter behavior, refresh semantics, and filter footer rendering all covered by state-level tests instead of brittle terminal snapshots.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/output/interactive.py tests/output/test_interactive.py
git commit -m "feat: add browser filtering and refresh"
```

## Task 3: Add Generic Preview Helpers And Bitbucket PR Compact Renderers

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/browser.py`
- Modify: `src/atlassian_cli/output/markdown.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Modify: `tests/output/test_markdown.py`
- Create: `tests/products/bitbucket/test_browser.py`
- Modify: `tests/products/bitbucket/test_pr_command.py`
- Modify: `tests/products/jira/test_issue_command.py`
- Test: `tests/output/test_markdown.py`
- Test: `tests/products/bitbucket/test_browser.py`
- Test: `tests/products/bitbucket/test_pr_command.py`
- Test: `tests/products/jira/test_issue_command.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/output/test_markdown.py`:

```python
from atlassian_cli.output.markdown import render_markdown_list_item, render_markdown_preview


def test_render_markdown_list_item_returns_single_scan_line() -> None:
    item = {
        "key": "PROJ-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Alice"},
    }

    rendered = render_markdown_list_item(item)

    assert rendered == "PROJ-1  Open  Alice  Example issue summary"


def test_render_markdown_preview_limits_description_excerpt() -> None:
    item = {
        "key": "PROJ-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Alice"},
        "description": "Line one\\nLine two\\nLine three\\nLine four",
        "links": {"self": "https://example.com"},
    }

    rendered = render_markdown_preview(item)

    assert "Status: Open" in rendered
    assert "Assignee: Alice" in rendered
    assert "Line four" not in rendered
    assert "links" not in rendered.lower()
```

Create `tests/products/bitbucket/test_browser.py`:

```python
from atlassian_cli.products.bitbucket.browser import (
    render_pull_request_item,
    render_pull_request_preview,
)


def test_render_pull_request_item_uses_dense_single_line_format() -> None:
    item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "sample-author"},
        "title": "[FEAT] DEMO-1234 example preview change",
    }

    rendered = render_pull_request_item(1, item)

    assert rendered == "24990  OPEN  sample-author  [FEAT] DEMO-1234 example preview change"
    assert "\n" not in rendered


def test_render_pull_request_preview_summarizes_reviewers_and_description() -> None:
    item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "sample-author"},
        "reviewers": [
            {"display_name": "Alice", "approved": True},
            {"display_name": "Bob", "approved": False},
            {"display_name": "Carol", "approved": False},
            {"display_name": "Dave", "approved": False},
        ],
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2026-04-27T13:19:55+00:00",
        "description": "Line one\\nLine two\\nLine three\\nLine four",
        "participants": [{"role": "PARTICIPANT"}],
        "links": {"self": "https://example.com/pr/24990"},
    }

    rendered = render_pull_request_preview(item)

    assert "Reviewers: Alice, Bob, Carol, +1 more" in rendered
    assert "From: feature/DEMO-1234/example-change" in rendered
    assert "To: main" in rendered
    assert "Updated: 2026-04-27 13:19:55" in rendered
    assert "Line four" not in rendered
    assert "participants" not in rendered.lower()
    assert "links" not in rendered.lower()
```

Append this test to `tests/products/bitbucket/test_pr_command.py`:

```python
def test_bitbucket_pr_list_interactive_source_uses_compact_preview_renderers(monkeypatch) -> None:
    from atlassian_cli.output.interactive import CollectionPage
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    sample_item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "sample-author"},
        "title": "[FEAT] DEMO-1234 example preview change",
        "reviewers": [
            {"display_name": "Alice"},
            {"display_name": "Bob"},
            {"display_name": "Carol"},
            {"display_name": "Dave"},
        ],
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2026-04-27T13:19:55+00:00",
        "description": "Line one\\nLine two\\nLine three\\nLine four",
    }
    captured: dict[str, str] = {}

    class FakeService:
        def list_page(self, project_key, repo_slug, state, start, limit):
            return CollectionPage(items=[sample_item], start=start, limit=limit, total=1)

        def get(self, project_key, repo_slug, pr_id):
            return sample_item

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(pr_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pr_module,
        "browse_collection",
        lambda source: captured.update(
            {
                "item": source.render_item(1, sample_item),
                "preview": source.render_preview(sample_item),
                "detail": source.render_detail(sample_item),
            }
        ),
    )

    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "list", "PROJ", "infra"],
    )

    assert result.exit_code == 0
    assert captured["item"] == "24990  OPEN  sample-author  [FEAT] DEMO-1234 example preview change"
    assert "Reviewers: Alice, Bob, Carol, +1 more" in captured["preview"]
    assert captured["detail"].startswith("# 24990 - [FEAT] DEMO-1234 example preview change")
```

Append this test to `tests/products/jira/test_issue_command.py`:

```python
def test_jira_issue_search_interactive_source_uses_generic_preview_renderer(monkeypatch) -> None:
    from atlassian_cli.output.interactive import CollectionPage
    from atlassian_cli.products.jira.commands import issue as issue_module

    sample_issue = {
        "key": "PROJ-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Alice"},
        "description": "Investigate rollout health",
    }
    captured: dict[str, str] = {}

    class FakeService:
        def search_page(self, jql, start, limit):
            return CollectionPage(items=[sample_issue], start=start, limit=limit, total=1)

        def get(self, issue_key):
            return sample_issue

    monkeypatch.setattr(issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService())
    monkeypatch.setattr(issue_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        issue_module,
        "browse_collection",
        lambda source: captured.update(
            {
                "item": source.render_item(1, sample_issue),
                "preview": source.render_preview(sample_issue),
            }
        ),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = PROJ"],
    )

    assert result.exit_code == 0
    assert captured["item"] == "PROJ-1  Open  Alice  Example issue summary"
    assert "Status: Open" in captured["preview"]
    assert "Assignee: Alice" in captured["preview"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/output/test_markdown.py tests/products/bitbucket/test_browser.py tests/products/bitbucket/test_pr_command.py tests/products/jira/test_issue_command.py -v`

Expected: FAIL because `render_markdown_list_item()` and `render_markdown_preview()` do not exist yet, `src/atlassian_cli/products/bitbucket/browser.py` does not exist, and interactive command wiring still uses the older renderer contract.

- [ ] **Step 3: Write the minimal implementation**

Add these helpers to `src/atlassian_cli/output/markdown.py` below `_heading()` and above `render_markdown()`:

```python
PREVIEW_FIELDS = (
    ("state", "State"),
    ("status", "Status"),
    ("author", "Author"),
    ("assignee", "Assignee"),
    ("reporter", "Reporter"),
    ("from_ref", "From"),
    ("to_ref", "To"),
    ("updated", "Updated"),
    ("updated_date", "Updated"),
)


def excerpt_text(value: Any, *, max_lines: int = 3) -> str:
    if value in (None, ""):
        return ""
    lines = [" ".join(line.split()) for line in str(value).splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join([*lines[: max_lines - 1], f"{lines[max_lines - 1]}..."])


def render_markdown_list_item(item: Mapping[str, Any]) -> str:
    identifier = next(
        (
            str(item[field])
            for field in ("key", "id", "slug", "name")
            if item.get(field) not in (None, "")
        ),
        "Item",
    )
    status = _inline_value(item.get("state") or item.get("status"))
    owner = _inline_value(item.get("author") or item.get("assignee"))
    title = next(
        (
            str(item[field])
            for field in ("summary", "title", "name")
            if item.get(field) not in (None, "")
        ),
        "",
    )
    return "  ".join(part for part in (identifier, status, owner, title) if part)


def render_markdown_preview(item: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for field, label in PREVIEW_FIELDS:
        text = _inline_value(item.get(field))
        if text:
            lines.append(f"{label}: {text}")

    description = excerpt_text(item.get("description"), max_lines=3)
    if description:
        lines.extend(["", "Description:", description])

    return "\n".join(lines) or _heading(item)
```

Create `src/atlassian_cli/products/bitbucket/browser.py`:

```python
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from atlassian_cli.output.markdown import excerpt_text, render_markdown, render_markdown_preview


def _user_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("display_name") or value.get("name") or "")
    return ""


def _reviewer_summary(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    names = [_user_name(item) for item in value if isinstance(item, Mapping)]
    names = [name for name in names if name]
    if len(names) <= 3:
        return ", ".join(names)
    return ", ".join([*names[:3], f"+{len(names) - 3} more"])


def _ref_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("display_id") or value.get("id") or "")
    return ""


def _format_updated(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value)
    if text.isdigit():
        timestamp = int(text)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


def render_pull_request_item(index: int, item: dict[str, Any]) -> str:
    parts = [
        str(item.get("id", "")).strip(),
        str(item.get("state", "")).strip(),
        _user_name(item.get("author")),
        str(item.get("title", "")).strip(),
    ]
    return "  ".join(part for part in parts if part)


def render_pull_request_preview(item: dict[str, Any]) -> str:
    lines: list[str] = []
    for label, value in (
        ("State", item.get("state")),
        ("Author", _user_name(item.get("author"))),
        ("Reviewers", _reviewer_summary(item.get("reviewers"))),
        ("From", _ref_name(item.get("from_ref"))),
        ("To", _ref_name(item.get("to_ref"))),
        ("Updated", _format_updated(item.get("updated_date"))),
    ):
        if value:
            lines.append(f"{label}: {value}")

    description = excerpt_text(item.get("description"), max_lines=3)
    if description:
        lines.extend(["", "Description:", description])

    return "\n".join(lines) or render_markdown_preview(item)


def render_pull_request_detail(item: dict[str, Any]) -> str:
    return render_markdown(item)
```

Update the interactive branch inside `src/atlassian_cli/products/bitbucket/commands/pr.py`:

```python
from atlassian_cli.output.interactive import InteractiveCollectionSource, browse_collection
from atlassian_cli.output.tty import should_use_interactive_output
from atlassian_cli.products.bitbucket.browser import (
    render_pull_request_detail,
    render_pull_request_item,
    render_pull_request_preview,
)


    if should_use_interactive_output(output, command_kind="collection"):
        browse_collection(
            InteractiveCollectionSource(
                title="Bitbucket pull requests",
                page_size=limit,
                fetch_page=lambda page_start, page_limit: service.list_page(
                    project_key,
                    repo_slug,
                    state,
                    page_start,
                    page_limit,
                ),
                fetch_detail=lambda item: service.get(project_key, repo_slug, item["id"]),
                render_item=render_pull_request_item,
                render_preview=render_pull_request_preview,
                render_detail=render_pull_request_detail,
                filter_text=lambda item: "\n".join(
                    [
                        render_pull_request_item(0, item),
                        render_pull_request_preview(item),
                    ]
                ),
            )
        )
        return
```

Update the interactive branch inside `src/atlassian_cli/products/jira/commands/issue.py`:

```python
from atlassian_cli.output.interactive import InteractiveCollectionSource, browse_collection
from atlassian_cli.output.markdown import (
    render_markdown,
    render_markdown_list_item,
    render_markdown_preview,
)
from atlassian_cli.output.tty import should_use_interactive_output


    if should_use_interactive_output(output, command_kind="collection"):
        browse_collection(
            InteractiveCollectionSource(
                title="Jira issue search",
                page_size=limit,
                fetch_page=lambda page_start, page_limit: service.search_page(
                    jql,
                    page_start,
                    page_limit,
                ),
                fetch_detail=lambda item: service.get(item["key"]),
                render_item=lambda index, item: render_markdown_list_item(item),
                render_preview=render_markdown_preview,
                render_detail=render_markdown,
                filter_text=lambda item: "\n".join(
                    [render_markdown_list_item(item), render_markdown_preview(item)]
                ),
            )
        )
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/output/test_markdown.py tests/products/bitbucket/test_browser.py tests/products/bitbucket/test_pr_command.py tests/products/jira/test_issue_command.py -v`

Expected: PASS with generic preview helpers available for non-Bitbucket collections and `bitbucket pr list` using the dense PR-specific list and preview renderers while still routing full detail through markdown.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/output/markdown.py src/atlassian_cli/products/bitbucket/browser.py src/atlassian_cli/products/bitbucket/commands/pr.py src/atlassian_cli/products/jira/commands/issue.py tests/output/test_markdown.py tests/products/bitbucket/test_browser.py tests/products/bitbucket/test_pr_command.py tests/products/jira/test_issue_command.py
git commit -m "feat: add compact pull request preview renderers"
```

## Task 4: Document The Interactive Preview Browser Contract

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_readme.py`:

```python
def test_readme_mentions_interactive_preview_browser() -> None:
    readme = Path("README.md").read_text()

    assert "live preview" in readme.lower()
    assert "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit" in readme
    assert "bottom preview" in readme.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_readme.py -v`

Expected: FAIL because the README does not yet describe the stacked list-plus-preview layout or the updated keybindings.

- [ ] **Step 3: Write the minimal documentation update**

Add this subsection to the interactive collection section in `README.md`:

```md
### Interactive browser behavior

TTY collection commands open a compact browser instead of printing a long static list.

- The top region is a dense single-line-per-item list for fast scanning.
- The bottom preview shows live metadata for the selected item without opening full detail.
- `Enter` opens the full markdown detail view for the selected item.
- `b` or `Esc` returns from detail to the list.
- `/` filters only the items already loaded into the current browser session.
- `r` refreshes the first page and returns the browser to list mode.

Keybindings:

`j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_readme.py -v`

Expected: PASS with the README explicitly documenting the live bottom preview, the detail-view handoff, and the interactive footer contract.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: describe interactive preview browser"
```
