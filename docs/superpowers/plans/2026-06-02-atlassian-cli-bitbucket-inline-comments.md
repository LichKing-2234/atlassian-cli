# Atlassian CLI Bitbucket Inline Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add line-aware Bitbucket pull request diff output and use those coordinates to create inline pull request comments.

**Architecture:** Keep the current command -> service -> provider -> schema -> renderer layering. Add a focused diff normalizer module for Bitbucket JSON diff payloads, extend provider methods for structured diff and anchored comment POSTs, and keep existing text diff and top-level comment behavior backward compatible.

**Tech Stack:** Python, Typer, atlassian-python-api Bitbucket client, Pydantic-style project schemas, pytest, ruff, live e2e through `tests/e2e/test_bitbucket_live.py`.

---

## File Structure

- Create `src/atlassian_cli/products/bitbucket/diff.py`
  - Normalizes Bitbucket Server/Data Center JSON diff payloads into stable files, hunks, lines, and optional inline-comment anchors.
- Modify `src/atlassian_cli/products/bitbucket/providers/base.py`
  - Adds `get_pull_request_diff_with_lines` and optional `anchor` support on `add_pull_request_comment`.
- Modify `src/atlassian_cli/products/bitbucket/providers/server.py`
  - Calls the JSON diff endpoint at `/pull-requests/{pr_id}/diff`.
  - Sends anchored comments with a direct POST when an anchor is supplied.
- Modify `src/atlassian_cli/products/bitbucket/services/pr.py`
  - Adds `diff_with_lines` and `diff_with_lines_raw`.
- Modify `src/atlassian_cli/products/bitbucket/services/pr_comment.py`
  - Carries optional inline anchors through normalized and raw add paths.
- Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`
  - Adds `--with-lines` to `bitbucket pr diff`.
- Modify `src/atlassian_cli/products/bitbucket/commands/pr_comment.py`
  - Adds `--path`, `--line`, and `--line-type` to `bitbucket pr comment add`.
- Modify tests:
  - `tests/products/bitbucket/test_provider.py`
  - `tests/products/bitbucket/test_pr_service.py`
  - `tests/products/bitbucket/test_pr_command.py`
  - `tests/products/bitbucket/test_pr_comment_service.py`
  - `tests/products/bitbucket/test_pr_comment_command.py`
  - `tests/e2e/test_bitbucket_live.py`
  - `tests/test_readme.py`
- Modify `README.md`
  - Adds examples and behavior notes.

`tests/e2e/coverage_manifest.py` should remain unchanged because this work adds options to existing command leaves: `bitbucket pr diff` and `bitbucket pr comment add`.

---

### Task 1: Provider Transport for Structured Diff and Anchored Comments

**Files:**
- Modify: `tests/products/bitbucket/test_provider.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`

- [ ] **Step 1: Write failing provider tests**

Add these tests near the existing pull request diff and comment provider tests in `tests/products/bitbucket/test_provider.py`:

```python
def test_bitbucket_provider_get_pull_request_diff_with_lines_uses_json_endpoint() -> None:
    calls = {}

    class FakeResponse:
        def json(self):
            return {
                "values": [
                    {
                        "destination": {"toString": "example.py"},
                        "hunks": [
                            {
                                "sourceLine": 0,
                                "sourceSpan": 0,
                                "destinationLine": 1,
                                "destinationSpan": 1,
                                "segments": [
                                    {
                                        "type": "ADDED",
                                        "lines": [
                                            {
                                                "destination": 1,
                                                "line": "+example response",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }

    class FakeClient:
        def _url_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> str:
            return f"rest/api/latest/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}"

        def get(self, url: str, headers=None, advanced_mode: bool = False):
            calls["args"] = (url, headers, advanced_mode)
            return FakeResponse()

    provider = build_provider_with_client(FakeClient())

    result = provider.get_pull_request_diff_with_lines("DEMO", "example-repo", 42)

    assert result["values"][0]["destination"]["toString"] == "example.py"
    assert calls["args"] == (
        "rest/api/latest/projects/DEMO/repos/example-repo/pull-requests/42/diff",
        {"Accept": "application/json"},
        True,
    )


def test_bitbucket_provider_add_pull_request_comment_posts_anchor_payload() -> None:
    calls = {}

    class FakeClient:
        def _url_pull_request_comments(self, project_key, repo_slug, pr_id):
            return (
                f"rest/api/latest/projects/{project_key}/repos/{repo_slug}"
                f"/pull-requests/{pr_id}/comments"
            )

        def post(self, url, data=None):
            calls["post"] = (url, data)
            return {"id": 1001, "text": data["text"], "anchor": data["anchor"]}

    provider = build_provider_with_client(FakeClient())

    result = provider.add_pull_request_comment(
        "DEMO",
        "example-repo",
        42,
        "example comment",
        anchor={"path": "example.py", "line": 12, "line_type": "ADDED"},
    )

    assert result["anchor"] == {"path": "example.py", "line": 12, "lineType": "ADDED"}
    assert calls["post"] == (
        "rest/api/latest/projects/DEMO/repos/example-repo/pull-requests/42/comments",
        {
            "text": "example comment",
            "anchor": {"path": "example.py", "line": 12, "lineType": "ADDED"},
        },
    )
```

- [ ] **Step 2: Run provider tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py -q
```

Expected: FAIL because `BitbucketServerProvider` does not have `get_pull_request_diff_with_lines`, and `add_pull_request_comment` does not accept `anchor`.

- [ ] **Step 3: Extend provider protocol**

Update the relevant methods in `src/atlassian_cli/products/bitbucket/providers/base.py`:

```python
    def get_pull_request_diff(self, project_key: str, repo_slug: str, pr_id: int) -> str: ...
    def get_pull_request_diff_with_lines(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict: ...
```

Change `add_pull_request_comment` in the same protocol to:

```python
    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        parent_id: str | None = None,
        anchor: dict | None = None,
    ) -> dict: ...
```

- [ ] **Step 4: Implement provider methods**

Update `src/atlassian_cli/products/bitbucket/providers/server.py`:

```python
    def get_pull_request_diff_with_lines(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict:
        url = f"{self.client._url_pull_request(project_key, repo_slug, pr_id)}/diff"
        response = self.client.get(
            url,
            headers={"Accept": "application/json"},
            advanced_mode=True,
        )
        if hasattr(response, "json"):
            return response.json()
        return response
```

Replace the existing `add_pull_request_comment` method with:

```python
    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        parent_id: str | None = None,
        anchor: dict | None = None,
    ) -> dict:
        if anchor is None:
            return self.client.add_pull_request_comment(
                project_key,
                repo_slug,
                pr_id,
                text,
                parent_id=parent_id,
            )

        body = {
            "text": text,
            "anchor": {
                "path": anchor["path"],
                "line": anchor["line"],
                "lineType": anchor["line_type"],
            },
        }
        if parent_id:
            body["parent"] = {"id": parent_id}

        url = self.client._url_pull_request_comments(project_key, repo_slug, pr_id)
        return self.client.post(url, data=body)
```

- [ ] **Step 5: Run provider tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_provider.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit provider transport**

Run:

```bash
git add tests/products/bitbucket/test_provider.py \
  src/atlassian_cli/products/bitbucket/providers/base.py \
  src/atlassian_cli/products/bitbucket/providers/server.py
git commit -m "feat: add bitbucket inline comment transport"
```

---

### Task 2: Structured Diff Normalization and Service Methods

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/diff.py`
- Create: `tests/products/bitbucket/test_pr_diff.py`
- Modify: `tests/products/bitbucket/test_pr_service.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/pr.py`

- [ ] **Step 1: Write diff normalizer tests**

Create `tests/products/bitbucket/test_pr_diff.py`:

```python
from atlassian_cli.products.bitbucket.diff import normalize_pull_request_diff


def test_normalize_pull_request_diff_builds_comment_anchors() -> None:
    raw = {
        "values": [
            {
                "destination": {"toString": "example.py"},
                "hunks": [
                    {
                        "sourceLine": 10,
                        "sourceSpan": 1,
                        "destinationLine": 10,
                        "destinationSpan": 2,
                        "segments": [
                            {
                                "type": "CONTEXT",
                                "lines": [
                                    {
                                        "source": 10,
                                        "destination": 10,
                                        "line": " unchanged",
                                    }
                                ],
                            },
                            {
                                "type": "ADDED",
                                "lines": [
                                    {
                                        "destination": 11,
                                        "line": "+example response",
                                    }
                                ],
                            },
                            {
                                "type": "REMOVED",
                                "lines": [
                                    {
                                        "source": 12,
                                        "line": "-example comment",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    result = normalize_pull_request_diff(42, raw)

    assert result == {
        "id": 42,
        "files": [
            {
                "path": "example.py",
                "hunks": [
                    {
                        "source_start": 10,
                        "source_span": 1,
                        "destination_start": 10,
                        "destination_span": 2,
                        "lines": [
                            {
                                "type": "CONTEXT",
                                "old_line": 10,
                                "new_line": 10,
                                "text": " unchanged",
                                "anchor": {
                                    "path": "example.py",
                                    "line": 10,
                                    "line_type": "CONTEXT",
                                },
                            },
                            {
                                "type": "ADDED",
                                "old_line": None,
                                "new_line": 11,
                                "text": "+example response",
                                "anchor": {
                                    "path": "example.py",
                                    "line": 11,
                                    "line_type": "ADDED",
                                },
                            },
                            {
                                "type": "REMOVED",
                                "old_line": 12,
                                "new_line": None,
                                "text": "-example comment",
                                "anchor": {
                                    "path": "example.py",
                                    "line": 12,
                                    "line_type": "REMOVED",
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_normalize_pull_request_diff_supports_component_paths_and_skips_metadata() -> None:
    raw = {
        "diffs": [
            {
                "source": {"components": ["src", "example.py"]},
                "hunks": [
                    {
                        "segments": [
                            {"type": "HEADER", "lines": [{"line": "@@ -1 +1 @@"}]},
                        ],
                    }
                ],
            }
        ]
    }

    result = normalize_pull_request_diff(42, raw)

    assert result == {
        "id": 42,
        "files": [
            {
                "path": "src/example.py",
                "hunks": [
                    {
                        "lines": [
                            {
                                "type": "HEADER",
                                "old_line": None,
                                "new_line": None,
                                "text": "@@ -1 +1 @@",
                            }
                        ]
                    }
                ],
            }
        ],
    }
```

- [ ] **Step 2: Write service tests**

Add these tests to `tests/products/bitbucket/test_pr_service.py`:

```python
def test_pull_request_service_diff_with_lines_normalizes_provider_payload() -> None:
    class StructuredDiffProvider(FakePullRequestProvider):
        def get_pull_request_diff_with_lines(self, project_key: str, repo_slug: str, pr_id: int):
            return {
                "values": [
                    {
                        "destination": {"toString": "example.py"},
                        "hunks": [
                            {
                                "sourceLine": 0,
                                "sourceSpan": 0,
                                "destinationLine": 1,
                                "destinationSpan": 1,
                                "segments": [
                                    {
                                        "type": "ADDED",
                                        "lines": [
                                            {
                                                "destination": 1,
                                                "line": "+example response",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }

    service = PullRequestService(provider=StructuredDiffProvider())

    result = service.diff_with_lines("DEMO", "example-repo", 42)

    assert result["id"] == 42
    assert result["files"][0]["path"] == "example.py"
    assert result["files"][0]["hunks"][0]["lines"][0]["anchor"] == {
        "path": "example.py",
        "line": 1,
        "line_type": "ADDED",
    }


def test_pull_request_service_diff_with_lines_raw_preserves_provider_payload() -> None:
    raw_payload = {"values": [{"destination": {"toString": "example.py"}}]}

    class StructuredDiffProvider(FakePullRequestProvider):
        def get_pull_request_diff_with_lines(self, project_key: str, repo_slug: str, pr_id: int):
            return raw_payload

    service = PullRequestService(provider=StructuredDiffProvider())

    assert service.diff_with_lines_raw("DEMO", "example-repo", 42) is raw_payload
```

- [ ] **Step 3: Run normalizer and service tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_pr_diff.py \
  tests/products/bitbucket/test_pr_service.py::test_pull_request_service_diff_with_lines_normalizes_provider_payload \
  tests/products/bitbucket/test_pr_service.py::test_pull_request_service_diff_with_lines_raw_preserves_provider_payload \
  -q
```

Expected: FAIL because `atlassian_cli.products.bitbucket.diff` and the service methods do not exist.

- [ ] **Step 4: Create diff normalizer**

Create `src/atlassian_cli/products/bitbucket/diff.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

COMMENTABLE_LINE_TYPES = {"ADDED", "REMOVED", "CONTEXT"}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _path_to_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        return ""

    for key in ("toString", "path", "displayId", "name"):
        item = value.get(key)
        if isinstance(item, str) and item:
            return item

    components = value.get("components")
    if isinstance(components, list):
        parts = [str(item) for item in components if str(item)]
        if parts:
            return "/".join(parts)

    parent = _path_to_string(value.get("parent"))
    name = value.get("name")
    if parent and isinstance(name, str) and name:
        return f"{parent}/{name}"
    if isinstance(name, str):
        return name
    return ""


def _file_path(file_data: Mapping[str, Any]) -> str:
    return (
        _path_to_string(file_data.get("destination"))
        or _path_to_string(file_data.get("source"))
        or _path_to_string(file_data.get("path"))
    )


def _line_number(data: Mapping[str, Any], *keys: str) -> int | None:
    value = _first_present(*(data.get(key) for key in keys))
    if value in (None, ""):
        return None
    return int(value)


def _line_text(data: Mapping[str, Any]) -> str:
    value = _first_present(data.get("line"), data.get("text"))
    return "" if value is None else str(value)


def _line_type(segment: Mapping[str, Any], line: Mapping[str, Any]) -> str:
    value = _first_present(line.get("type"), segment.get("type"), "")
    return str(value).upper()


def _anchor(path: str, line_type: str, old_line: int | None, new_line: int | None) -> dict | None:
    if line_type not in COMMENTABLE_LINE_TYPES:
        return None
    if line_type == "REMOVED":
        line = old_line
    else:
        line = new_line if new_line is not None else old_line
    if not path or line is None:
        return None
    return {"path": path, "line": line, "line_type": line_type}


def _normalize_line(
    *,
    path: str,
    segment: Mapping[str, Any],
    line: Mapping[str, Any],
) -> dict[str, Any]:
    line_type = _line_type(segment, line)
    old_line = _line_number(line, "source", "sourceLine", "oldLine", "old_line")
    new_line = _line_number(
        line,
        "destination",
        "destinationLine",
        "newLine",
        "new_line",
    )
    if line_type == "ADDED":
        old_line = None
    elif line_type == "REMOVED":
        new_line = None

    payload: dict[str, Any] = {
        "type": line_type,
        "old_line": old_line,
        "new_line": new_line,
        "text": _line_text(line),
    }
    anchor = _anchor(path, line_type, old_line, new_line)
    if anchor:
        payload["anchor"] = anchor
    return payload


def _normalize_hunk(path: str, hunk: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_start": _line_number(hunk, "sourceLine", "source_start"),
        "source_span": _line_number(hunk, "sourceSpan", "source_span"),
        "destination_start": _line_number(hunk, "destinationLine", "destination_start"),
        "destination_span": _line_number(hunk, "destinationSpan", "destination_span"),
    }

    lines: list[dict[str, Any]] = []
    for segment in hunk.get("segments", []):
        if not isinstance(segment, Mapping):
            continue
        for line in segment.get("lines", []):
            if isinstance(line, Mapping):
                lines.append(_normalize_line(path=path, segment=segment, line=line))

    payload["lines"] = lines
    return {key: value for key, value in payload.items() if value not in (None, [], {})}


def normalize_pull_request_diff(pr_id: int, data: Mapping[str, Any]) -> dict[str, Any]:
    files = []
    raw_files = data.get("values")
    if raw_files is None:
        raw_files = data.get("diffs", [])

    for file_data in raw_files:
        if not isinstance(file_data, Mapping):
            continue
        path = _file_path(file_data)
        hunks = [
            _normalize_hunk(path, hunk)
            for hunk in file_data.get("hunks", [])
            if isinstance(hunk, Mapping)
        ]
        files.append({"path": path, "hunks": hunks})

    return {"id": pr_id, "files": files}
```

- [ ] **Step 5: Add service methods**

Modify `src/atlassian_cli/products/bitbucket/services/pr.py`:

```python
from atlassian_cli.products.bitbucket.diff import normalize_pull_request_diff
```

Add these methods to `PullRequestService`:

```python
    def diff_with_lines(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return normalize_pull_request_diff(
            pr_id,
            self.provider.get_pull_request_diff_with_lines(project_key, repo_slug, pr_id),
        )

    def diff_with_lines_raw(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.get_pull_request_diff_with_lines(project_key, repo_slug, pr_id)
```

- [ ] **Step 6: Run normalizer and service tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_pr_diff.py \
  tests/products/bitbucket/test_pr_service.py::test_pull_request_service_diff_with_lines_normalizes_provider_payload \
  tests/products/bitbucket/test_pr_service.py::test_pull_request_service_diff_with_lines_raw_preserves_provider_payload \
  -q
```

Expected: PASS.

- [ ] **Step 7: Commit structured diff service**

Run:

```bash
git add src/atlassian_cli/products/bitbucket/diff.py \
  src/atlassian_cli/products/bitbucket/services/pr.py \
  tests/products/bitbucket/test_pr_diff.py \
  tests/products/bitbucket/test_pr_service.py
git commit -m "feat: add bitbucket line-aware diff service"
```

---

### Task 3: `pr diff --with-lines` Command Wiring

**Files:**
- Modify: `tests/products/bitbucket/test_pr_command.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`

- [ ] **Step 1: Write failing command tests**

Add these tests near the existing `test_bitbucket_pr_diff_outputs_markdown_diff_detail` test in `tests/products/bitbucket/test_pr_command.py`:

```python
def test_bitbucket_pr_diff_with_lines_outputs_structured_json(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def diff_with_lines(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {
                "id": pr_id,
                "files": [
                    {
                        "path": "example.py",
                        "hunks": [
                            {
                                "lines": [
                                    {
                                        "type": "ADDED",
                                        "new_line": 1,
                                        "text": "+example response",
                                        "anchor": {
                                            "path": "example.py",
                                            "line": 1,
                                            "line_type": "ADDED",
                                        },
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
            "--with-lines",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"line_type": "ADDED"' in result.stdout


def test_bitbucket_pr_diff_with_lines_raw_output_uses_raw_service(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr as pr_module

    calls = {}

    class FakeService:
        def diff_with_lines_raw(self, project_key, repo_slug, pr_id):
            calls["args"] = (project_key, repo_slug, pr_id)
            return {"values": [{"destination": {"toString": "example.py"}}]}

    monkeypatch.setattr(pr_module, "build_pr_service", lambda *_args: FakeService())

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "diff",
            "DEMO",
            "example-repo",
            "42",
            "--with-lines",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert calls["args"] == ("DEMO", "example-repo", 42)
    assert '"values"' in result.stdout
```

- [ ] **Step 2: Run command tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_pr_command.py::test_bitbucket_pr_diff_with_lines_outputs_structured_json \
  tests/products/bitbucket/test_pr_command.py::test_bitbucket_pr_diff_with_lines_raw_output_uses_raw_service \
  -q
```

Expected: FAIL because `--with-lines` is not defined.

- [ ] **Step 3: Add command option and dispatch**

Modify `get_pull_request_diff` in `src/atlassian_cli/products/bitbucket/commands/pr.py`:

```python
@app.command("diff")
def get_pull_request_diff(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    with_lines: bool = typer.Option(False, "--with-lines"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_pr_service(ctx.obj)
    if with_lines:
        payload = (
            service.diff_with_lines_raw(project_key, repo_slug, pr_id)
            if is_raw_output(output)
            else service.diff_with_lines(project_key, repo_slug, pr_id)
        )
        typer.echo(render_output(payload, output=output))
        return

    if is_raw_output(output):
        typer.echo(render_output(service.diff_raw(project_key, repo_slug, pr_id), output=output))
        return

    payload = service.get_detail(project_key, repo_slug, pr_id)
    if normalized_output(output) == OutputMode.MARKDOWN:
        typer.echo(
            render_pull_request_detail(
                payload,
                colorize_diff=should_use_color_output(output),
            )
        )
        return

    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Run command tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_pr_command.py::test_bitbucket_pr_diff_outputs_markdown_diff_detail \
  tests/products/bitbucket/test_pr_command.py::test_bitbucket_pr_diff_outputs_colored_diff_for_tty \
  tests/products/bitbucket/test_pr_command.py::test_bitbucket_pr_diff_with_lines_outputs_structured_json \
  tests/products/bitbucket/test_pr_command.py::test_bitbucket_pr_diff_with_lines_raw_output_uses_raw_service \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit diff command wiring**

Run:

```bash
git add tests/products/bitbucket/test_pr_command.py \
  src/atlassian_cli/products/bitbucket/commands/pr.py
git commit -m "feat: expose bitbucket line-aware diff"
```

---

### Task 4: Inline Comment Service and Command Wiring

**Files:**
- Modify: `tests/products/bitbucket/test_pr_comment_service.py`
- Modify: `tests/products/bitbucket/test_pr_comment_command.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/pr_comment.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr_comment.py`

- [ ] **Step 1: Write failing service tests**

Update `FakeCommentProvider.add_pull_request_comment` in `tests/products/bitbucket/test_pr_comment_service.py`:

```python
    def add_pull_request_comment(
        self,
        project_key,
        repo_slug,
        pr_id,
        text,
        *,
        parent_id=None,
        anchor=None,
    ):
        self.calls.append(("add", project_key, repo_slug, pr_id, text, parent_id, anchor))
        payload = {"id": 1002, "version": 1, "text": text}
        if anchor:
            payload["anchor"] = {
                "path": anchor["path"],
                "line": anchor["line"],
                "lineType": anchor["line_type"],
            }
        return payload
```

Add this test after `test_comment_service_get_add_reply_edit_and_delete`:

```python
def test_comment_service_adds_inline_comment_anchor() -> None:
    provider = FakeCommentProvider()
    service = PullRequestCommentService(provider)

    result = service.add(
        "DEMO",
        "example-repo",
        42,
        "example comment",
        anchor={"path": "example.py", "line": 12, "line_type": "ADDED"},
    )

    assert result["anchor"] == {"path": "example.py", "line": 12, "line_type": "ADDED"}
    assert provider.calls[-1] == (
        "add",
        "DEMO",
        "example-repo",
        42,
        "example comment",
        None,
        {"path": "example.py", "line": 12, "line_type": "ADDED"},
    )
```

Update `test_comment_service_raw_methods_preserve_provider_payloads` so the raw add assertion uses the new optional signature:

```python
    assert (
        service.add_raw(
            "DEMO",
            "example-repo",
            42,
            "example comment",
            anchor={"path": "example.py", "line": 12, "line_type": "ADDED"},
        )["anchor"]["lineType"]
        == "ADDED"
    )
```

- [ ] **Step 2: Write failing command tests**

Update `FakeCommentService.add` and `FakeCommentService.add_raw` in `tests/products/bitbucket/test_pr_comment_command.py`:

```python
    def add(self, project_key, repo_slug, pr_id, text, anchor=None):
        payload = {"id": "1002", "text": text}
        if anchor:
            payload["anchor"] = anchor
        return payload

    def add_raw(self, project_key, repo_slug, pr_id, text, anchor=None):
        payload = {"id": 1002, "text": text}
        if anchor:
            payload["anchor"] = {
                "path": anchor["path"],
                "line": anchor["line"],
                "lineType": anchor["line_type"],
            }
        return payload
```

Add these tests after `test_bitbucket_pr_comment_raw_output_uses_raw_service`:

```python
def test_bitbucket_pr_comment_add_accepts_inline_anchor(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    monkeypatch.setattr(
        comment_module, "build_comment_service", lambda *_args: FakeCommentService()
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "add",
            "DEMO",
            "example-repo",
            "42",
            "example comment",
            "--path",
            "example.py",
            "--line",
            "12",
            "--line-type",
            "added",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"path": "example.py"' in result.stdout
    assert '"line": 12' in result.stdout
    assert '"line_type": "ADDED"' in result.stdout


def test_bitbucket_pr_comment_add_rejects_partial_inline_anchor(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    service_calls = []

    def build_service(*_args):
        service_calls.append("built")
        return FakeCommentService()

    monkeypatch.setattr(comment_module, "build_comment_service", build_service)

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "add",
            "DEMO",
            "example-repo",
            "42",
            "example comment",
            "--path",
            "example.py",
        ],
    )

    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert service_calls == []


def test_bitbucket_pr_comment_add_rejects_invalid_line_type(monkeypatch) -> None:
    from atlassian_cli.products.bitbucket.commands import pr_comment as comment_module

    service_calls = []
    monkeypatch.setattr(
        comment_module,
        "build_comment_service",
        lambda *_args: service_calls.append("built") or FakeCommentService(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "pr",
            "comment",
            "add",
            "DEMO",
            "example-repo",
            "42",
            "example comment",
            "--path",
            "example.py",
            "--line",
            "12",
            "--line-type",
            "SIDEWAYS",
        ],
    )

    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert service_calls == []
```

- [ ] **Step 3: Run comment tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_pr_comment_service.py \
  tests/products/bitbucket/test_pr_comment_command.py \
  -q
```

Expected: FAIL because the service and command do not accept anchor arguments.

- [ ] **Step 4: Update comment service**

Modify `PullRequestCommentService.add` and `add_raw` in `src/atlassian_cli/products/bitbucket/services/pr_comment.py`:

```python
    def add(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        anchor: dict | None = None,
    ) -> dict:
        return BitbucketPullRequestComment.from_api_response(
            self.provider.add_pull_request_comment(
                project_key,
                repo_slug,
                pr_id,
                text,
                anchor=anchor,
            )
        ).to_simplified_dict()

    def add_raw(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        anchor: dict | None = None,
    ) -> dict:
        return self.provider.add_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            text,
            anchor=anchor,
        )
```

Update `reply` and `reply_raw` provider calls to pass an explicit `anchor=None` only if needed by type checkers. The runtime behavior should remain:

```python
            self.provider.add_pull_request_comment(
                project_key,
                repo_slug,
                pr_id,
                text,
                parent_id=parent_id,
            )
```

- [ ] **Step 5: Update comment command validation**

Add this helper near `build_comment_service` in `src/atlassian_cli/products/bitbucket/commands/pr_comment.py`:

```python
INLINE_LINE_TYPES = {"ADDED", "REMOVED", "CONTEXT"}


def _inline_anchor(path: str | None, line: int | None, line_type: str | None) -> dict | None:
    provided = [path is not None, line is not None, line_type is not None]
    if any(provided) and not all(provided):
        raise typer.BadParameter(
            "--path, --line, and --line-type must be supplied together",
            param_hint="--path",
        )
    if not any(provided):
        return None
    if line is None or line <= 0:
        raise typer.BadParameter("--line must be a positive integer", param_hint="--line")

    normalized_line_type = str(line_type).upper()
    if normalized_line_type not in INLINE_LINE_TYPES:
        raise typer.BadParameter(
            "--line-type must be ADDED, REMOVED, or CONTEXT",
            param_hint="--line-type",
        )

    return {"path": path, "line": line, "line_type": normalized_line_type}
```

Update `add_comment` in the same file:

```python
@app.command("add")
def add_comment(
    ctx: typer.Context,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    text: str,
    path: str | None = typer.Option(None, "--path"),
    line: int | None = typer.Option(None, "--line"),
    line_type: str | None = typer.Option(None, "--line-type"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    anchor = _inline_anchor(path, line, line_type)
    service = build_comment_service(ctx.obj)
    payload = (
        service.add_raw(project_key, repo_slug, pr_id, text, anchor=anchor)
        if is_raw_output(output)
        else service.add(project_key, repo_slug, pr_id, text, anchor=anchor)
    )
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 6: Run comment tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_pr_comment_service.py \
  tests/products/bitbucket/test_pr_comment_command.py \
  -q
```

Expected: PASS.

- [ ] **Step 7: Commit inline comment command**

Run:

```bash
git add tests/products/bitbucket/test_pr_comment_service.py \
  tests/products/bitbucket/test_pr_comment_command.py \
  src/atlassian_cli/products/bitbucket/services/pr_comment.py \
  src/atlassian_cli/products/bitbucket/commands/pr_comment.py
git commit -m "feat: support bitbucket inline comments"
```

---

### Task 5: README, README Tests, and Live E2E Coverage

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Modify: `tests/e2e/test_bitbucket_live.py`

- [ ] **Step 1: Write README test update**

Update `test_readme_mentions_bitbucket_pr_diff_tty_behavior` in `tests/test_readme.py`:

```python
def test_readme_mentions_bitbucket_pr_diff_tty_behavior() -> None:
    readme = Path("README.md").read_text()

    assert "bitbucket pr diff demo example-repo 42" in readme.lower()
    assert "bitbucket pr diff demo example-repo 42 --with-lines" in readme.lower()
    assert "ansi-colored diff output in a tty" in readme.lower()
    assert "falls back to plain text" in readme.lower()
    assert "line-aware diff output" in readme.lower()
```

Update `test_readme_mentions_bitbucket_comments_and_build_status`:

```python
def test_readme_mentions_bitbucket_comments_and_build_status() -> None:
    readme = Path("README.md").read_text()

    assert "bitbucket pr comment list demo example-repo 42" in readme.lower()
    assert (
        "bitbucket pr comment add demo example-repo 42 \"example comment\" --path example.py"
        in readme.lower()
    )
    assert "bitbucket pr build-status demo example-repo 42" in readme.lower()
    assert "bitbucket commit build-status abc123" in readme.lower()
```

- [ ] **Step 2: Write live e2e update**

In `tests/e2e/test_bitbucket_live.py`, after the existing `diff_payload` assertions, add:

```python
    diff_with_lines = run_json(
        live_env,
        "bitbucket",
        "pr",
        "diff",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "--with-lines",
        "--output",
        "json",
    )
    assert diff_with_lines["id"] == pr_id

    inline_anchor = None
    for file_diff in diff_with_lines["files"]:
        if file_diff.get("path") != "e2e-note.txt":
            continue
        for hunk in file_diff.get("hunks", []):
            for line in hunk.get("lines", []):
                anchor = line.get("anchor")
                if anchor and anchor.get("line_type") == "ADDED":
                    inline_anchor = anchor
                    break
            if inline_anchor:
                break
        if inline_anchor:
            break
    assert inline_anchor is not None
```

After the existing top-level `added_comment` block and before listing comments, add:

```python
    inline_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "add",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        "example comment",
        "--path",
        inline_anchor["path"],
        "--line",
        str(inline_anchor["line"]),
        "--line-type",
        inline_anchor["line_type"],
        "--output",
        "json",
    )
    inline_comment_id = inline_comment["id"]
    inline_comment_version = inline_comment["version"]
    assert inline_comment["anchor"]["path"] == inline_anchor["path"]
    assert inline_comment["anchor"]["line"] == inline_anchor["line"]
    assert inline_comment["anchor"]["line_type"] == inline_anchor["line_type"]
```

After the existing `deleted_reply` assertion and before build-status checks, delete the inline comment:

```python
    deleted_inline_comment = run_json(
        live_env,
        "bitbucket",
        "pr",
        "comment",
        "delete",
        target["project_key"],
        target["repo_slug"],
        str(pr_id),
        inline_comment_id,
        "--version",
        str(inline_comment_version),
        "--output",
        "json",
    )
    assert deleted_inline_comment["deleted"] is True
```

- [ ] **Step 3: Run README and live-test syntax checks and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -q
.venv/bin/python -m pytest tests/e2e/test_bitbucket_live.py --collect-only -q
```

Expected: README tests fail because README has not been updated. E2E collect should pass.

- [ ] **Step 4: Update README examples and behavior text**

In `README.md`, add examples near the existing Bitbucket examples:

```markdown
- `atlassian bitbucket pr diff DEMO example-repo 42 --with-lines --output json`
- `atlassian bitbucket pr comment add DEMO example-repo 42 "example comment" --path example.py --line 12 --line-type ADDED`
```

In the "Bitbucket pull request diff behavior" section, add:

```markdown
- `atlassian bitbucket pr diff DEMO example-repo 42 --with-lines --output json` returns line-aware diff output with old and new line coordinates and reusable inline-comment anchors.
```

In the "Bitbucket pull request comments and build status behavior" section, add:

```markdown
- `atlassian bitbucket pr comment add DEMO example-repo 42 "example comment" --path example.py --line 12 --line-type ADDED` creates an inline pull request comment.
```

- [ ] **Step 5: Scan public examples for real-looking identifiers**

Run:

```bash
rg -n "https://[^ ]+|[A-Z]{2,}-[0-9]+|@[A-Za-z0-9_.-]+|feature/[A-Za-z0-9_-]+/.+" \
  README.md docs tests
```

Expected: Existing approved placeholders such as `DEMO-1`, `DEMO-1234`, `feature/DEMO-1234/example-change`, `https://bitbucket.example.com`, and `example-user-id` may appear. New additions should use only `DEMO`, `example-repo`, `example.py`, and `example comment`.

- [ ] **Step 6: Run README tests and e2e collection and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_readme.py -q
.venv/bin/python -m pytest tests/e2e/test_bitbucket_live.py --collect-only -q
.venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit docs and e2e coverage**

Run:

```bash
git add README.md tests/test_readme.py tests/e2e/test_bitbucket_live.py
git commit -m "docs: document bitbucket inline comments"
```

---

### Task 6: Full Verification and Live E2E

**Files:**
- Verify repository state only.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_provider.py \
  tests/products/bitbucket/test_pr_diff.py \
  tests/products/bitbucket/test_pr_service.py \
  tests/products/bitbucket/test_pr_command.py \
  tests/products/bitbucket/test_pr_comment_service.py \
  tests/products/bitbucket/test_pr_comment_command.py \
  tests/test_readme.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run required repository verification**

Run:

```bash
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: all commands PASS.

- [ ] **Step 3: Run affected live e2e path**

Run:

```bash
ATLASSIAN_E2E=1 .venv/bin/python -m pytest \
  tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live \
  -q
```

Expected: PASS in an available live Bitbucket Server/Data Center e2e environment.

If this command fails because live credentials or the live Bitbucket environment are unavailable, report that blocker explicitly and do not call the feature live-verified.

- [ ] **Step 4: Inspect final diff and untracked files**

Run:

```bash
git status --short --branch
git diff --stat origin/main...HEAD
```

Expected: only intended Bitbucket inline comment changes plus already-existing unrelated workspace state. Do not stage or remove unrelated files such as a pre-existing untracked `uv.lock`.

- [ ] **Step 5: Confirm implementation history is complete**

Run:

```bash
git log --oneline -8
```

Expected: the history includes the task commits from Tasks 1 through 5. If verification did not require follow-up fixes, leave that implementation history unchanged.
