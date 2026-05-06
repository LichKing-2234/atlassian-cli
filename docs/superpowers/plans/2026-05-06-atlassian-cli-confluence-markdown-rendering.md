# Confluence Markdown Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Confluence page `content.value` as readable Markdown in `--output markdown` when the content contains Confluence storage HTML, without changing normalized or raw machine-readable payloads.

**Architecture:** Keep the behavior entirely inside the markdown render path. Detect HTML-like page content at render time, convert it with `markdownify`, and leave existing plain text or Markdown content unchanged. Verify both the renderer and the `confluence page get` command output path, then document the user-visible behavior in `README.md`.

**Tech Stack:** Python, Typer, pytest, markdownify, Ruff

---

## File Map

- Modify: `pyproject.toml`
  - Add `markdownify` as a runtime dependency.
- Modify: `src/atlassian_cli/output/markdown.py:1-188`
  - Add HTML detection and conversion helpers used only by markdown detail rendering.
- Modify: `tests/output/test_markdown.py:1-117`
  - Add renderer-level regression tests for Confluence storage HTML conversion and plain Markdown pass-through.
- Modify: `tests/products/confluence/test_page_command.py:1-320`
  - Add a command-level regression test proving `confluence page get` markdown output no longer prints raw storage tags.
- Modify: `README.md:68-87`
  - Document that markdown detail output renders Confluence page content into readable Markdown while machine-readable outputs stay structured.

### Task 1: Write the Failing Regression Tests

**Files:**
- Modify: `tests/output/test_markdown.py:92-117`
- Modify: `tests/products/confluence/test_page_command.py:1-120`

- [ ] **Step 1: Add a renderer test for Confluence storage HTML conversion**

Add this test near the existing page envelope assertions in `tests/output/test_markdown.py`:

```python
def test_render_markdown_converts_confluence_storage_html_content() -> None:
    rendered = render_markdown(
        {
            "metadata": {"id": "1234", "title": "Example Page", "version": 2},
            "content": {
                "value": (
                    "<p>Intro <a href=\"https://example.com\">example link</a></p>"
                    "<ol><li>First step</li><li>Second step</li></ol>"
                )
            },
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
    assert "<p>" not in rendered
    assert "<ol>" not in rendered
    assert "[example link](https://example.com)" in rendered
    assert "1. First step" in rendered
    assert "2. Second step" in rendered
```

- [ ] **Step 2: Add a renderer test proving existing Markdown is not re-processed**

Add this second test in `tests/output/test_markdown.py`:

```python
def test_render_markdown_leaves_existing_markdown_content_unchanged() -> None:
    rendered = render_markdown(
        {
            "metadata": {"id": "1234", "title": "Example Page", "version": 2},
            "content": {"value": "## Runbook\n\n- Use the checklist."},
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
    assert "## Runbook" in rendered
    assert "- Use the checklist." in rendered
```

- [ ] **Step 3: Add a command-level regression test for markdown page output**

Add this test near the existing `page get` command tests in `tests/products/confluence/test_page_command.py`:

```python
def test_confluence_page_get_renders_storage_html_in_markdown_output(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import page as page_module

    monkeypatch.setattr(
        page_module,
        "build_page_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get": lambda self, page_id, **kwargs: {
                    "metadata": {"id": page_id, "title": "Example Page"},
                    "content": {
                        "value": (
                            "<p>Intro <a href=\"https://example.com\">example link</a></p>"
                            "<ac:structured-macro ac:name=\"info\">"
                            "<ac:rich-text-body><p>Example note</p></ac:rich-text-body>"
                            "</ac:structured-macro>"
                        )
                    },
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
            "page",
            "get",
            "1234",
            "--output",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert "<p>" not in result.stdout
    assert "ac:structured-macro" not in result.stdout
    assert "[example link](https://example.com)" in result.stdout
    assert "Example note" in result.stdout
```

- [ ] **Step 4: Run the targeted tests to verify they fail for the right reason**

Run:

```bash
.venv/bin/python -m pytest -q tests/output/test_markdown.py tests/products/confluence/test_page_command.py -k "markdown or page_get_renders_storage_html"
```

Expected:

- the new renderer test fails because `render_markdown()` still returns raw `<p>` / `<ol>` HTML
- the new command test fails because `confluence page get --output markdown` still prints raw storage tags

- [ ] **Step 5: Commit the failing-test checkpoint**

Run:

```bash
git add tests/output/test_markdown.py tests/products/confluence/test_page_command.py
git commit -m "test: cover Confluence markdown rendering"
```

### Task 2: Implement Markdown Rendering with the Minimal Runtime Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/atlassian_cli/output/markdown.py:1-188`

- [ ] **Step 1: Add `markdownify` as a runtime dependency**

Update the dependency list in `pyproject.toml`:

```toml
dependencies = [
  "atlassian-python-api>=4.0.7",
  "markdownify>=1.2.2",
  "prompt_toolkit>=3.0.51",
  "pydantic>=2.12.0",
  "PyYAML>=6.0.2",
  "rich>=14.0.0",
  "typer>=0.16.0",
]
```

- [ ] **Step 2: Add HTML detection and conversion helpers in the markdown renderer**

Add imports and helpers near the top of `src/atlassian_cli/output/markdown.py`:

```python
import re
from collections.abc import Mapping, Sequence
from typing import Any

from markdownify import markdownify as convert_html_to_markdown

HTML_CONTENT_RE = re.compile(
    r"<(?:p|br|a|table|thead|tbody|tr|th|td|ol|ul|li)\\b|<(?:ac|ri):",
    re.IGNORECASE,
)


def _normalize_markdown_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _render_detail_body(field: str, value: Any) -> str:
    text = _inline_value(value)
    if field != "content" or not text:
        return text
    if not HTML_CONTENT_RE.search(text):
        return text
    rendered = convert_html_to_markdown(text, heading_style="ATX")
    return _normalize_markdown_block(rendered)
```

- [ ] **Step 3: Route detail-body rendering through the helper**

Replace the current body-field loop in `render_markdown()`:

```python
    for field in DETAIL_BODY_FIELDS:
        text = _render_detail_body(field, value.get(field))
        if text:
            lines.extend(["", f"## {field.title()}", text])
```

This keeps list output and preview rendering unchanged and limits conversion to detail content blocks.

- [ ] **Step 4: Run the same targeted tests to verify they now pass**

Run:

```bash
.venv/bin/python -m pytest -q tests/output/test_markdown.py tests/products/confluence/test_page_command.py -k "markdown or page_get_renders_storage_html"
```

Expected:

- all selected tests pass
- the new assertions show HTML tags are removed from markdown output while existing Markdown still renders unchanged

- [ ] **Step 5: Commit the implementation checkpoint**

Run:

```bash
git add pyproject.toml src/atlassian_cli/output/markdown.py tests/output/test_markdown.py tests/products/confluence/test_page_command.py
git commit -m "fix: render Confluence page content as markdown"
```

### Task 3: Update User-Facing Docs and Run Full Verification

**Files:**
- Modify: `README.md:68-87`

- [ ] **Step 1: Document the behavior in `README.md`**

Add one concise bullet under `## Output Modes`:

```md
- Confluence page detail output renders storage HTML content into readable Markdown in `--output markdown`.
```

Keep the note scoped to human-readable markdown behavior and do not imply that `json` or `yaml` are transformed.

- [ ] **Step 2: Run formatter, tests, and lint checks required by the repository**

Run:

```bash
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected:

- `ruff format --check .` exits `0`
- `pytest` exits `0`
- `ruff check ...` exits `0`

- [ ] **Step 3: Commit the documentation and verification-complete state**

Run:

```bash
git add README.md
git commit -m "docs: note Confluence markdown rendering"
```

- [ ] **Step 4: Summarize the outcome with verification evidence**

Report:

- which files changed
- which targeted tests proved the renderer change
- the exit status of the three repository verification commands
