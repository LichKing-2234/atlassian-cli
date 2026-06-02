# Atlassian CLI Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class Jira issue attachment commands and Confluence page-scoped attachment command aliases while preserving existing Confluence attachment commands.

**Architecture:** Follow the existing `command -> service -> provider -> schema -> renderer` flow. Add a focused Jira attachment schema/service/command layer, extend provider protocols for attachment methods, and reuse the existing Confluence attachment service behind both old and new command paths.

**Tech Stack:** Python 3.13 in the repository virtualenv, Typer, pydantic, atlassian-python-api, pytest, ruff.

---

## File Structure

- Modify `src/atlassian_cli/products/jira/schemas.py`: add `JiraAttachment`.
- Modify `src/atlassian_cli/products/jira/providers/base.py`: add attachment protocol methods.
- Modify `src/atlassian_cli/products/jira/providers/server.py`: implement Jira attachment list/upload/download.
- Create `src/atlassian_cli/products/jira/services/attachment.py`: normalize Jira attachment workflows.
- Create `src/atlassian_cli/products/jira/commands/attachment.py`: expose `jira issue attachment` commands.
- Modify `src/atlassian_cli/products/jira/commands/issue.py`: register the nested attachment Typer app.
- Modify `src/atlassian_cli/products/confluence/providers/base.py`: add list/upload options and page-scoped download protocol.
- Modify `src/atlassian_cli/products/confluence/providers/server.py`: forward Confluence attachment options and page-scoped download by name.
- Modify `src/atlassian_cli/products/confluence/services/attachment.py`: support filters, upload comments, and page-scoped download.
- Modify `src/atlassian_cli/products/confluence/commands/attachment.py`: add shared list/upload options without breaking old arguments.
- Create `src/atlassian_cli/products/confluence/commands/page_attachment.py`: expose `confluence page attachment` commands.
- Modify `src/atlassian_cli/products/confluence/commands/page.py`: register the nested attachment Typer app.
- Modify `tests/products/jira/test_schemas.py`: add Jira attachment schema coverage.
- Modify `tests/products/jira/test_provider.py`: add Jira provider attachment coverage.
- Create `tests/products/jira/test_attachment_service.py`: add Jira attachment service coverage.
- Create `tests/products/jira/test_attachment_command.py`: add Jira attachment command coverage.
- Modify `tests/products/confluence/test_provider.py`: add Confluence option and page-scoped download coverage.
- Modify `tests/products/confluence/test_attachment_service.py`: add Confluence service coverage for filters and page-scoped download.
- Modify `tests/products/confluence/test_attachment_command.py`: add top-level option coverage.
- Modify `tests/products/confluence/test_page_command.py`: add page attachment alias coverage.
- Modify `tests/test_cli_help.py`: ensure new nested help is discoverable.
- Modify `tests/e2e/coverage_manifest.py`: add new leaf commands.
- Modify `tests/e2e/test_jira_live.py`: exercise Jira attachment upload/list/download.
- Modify `tests/e2e/test_confluence_live.py`: exercise Confluence page attachment aliases.
- Modify `README.md`: document public-safe command examples.

### Task 1: Add Jira Attachment Schema

**Files:**
- Modify: `tests/products/jira/test_schemas.py`
- Modify: `src/atlassian_cli/products/jira/schemas.py`

- [ ] **Step 1: Write the failing schema test**

Append this test to `tests/products/jira/test_schemas.py`:

```python
from atlassian_cli.products.jira.schemas import JiraAttachment


def test_jira_attachment_schema_normalizes_metadata() -> None:
    attachment = JiraAttachment.from_api_response(
        {
            "id": "10001",
            "filename": "report.pdf",
            "size": 42,
            "mimeType": "application/pdf",
            "created": "2026-06-02T01:02:03.000+0000",
            "content": "attachment://DEMO-1/report.pdf",
            "author": {
                "displayName": "Example Author",
                "name": "example-user-id",
            },
        }
    )

    assert attachment.to_simplified_dict() == {
        "id": "10001",
        "filename": "report.pdf",
        "size": 42,
        "mime_type": "application/pdf",
        "created": "2026-06-02T01:02:03.000+0000",
        "download_url": "attachment://DEMO-1/report.pdf",
        "author": {
            "display_name": "Example Author",
            "name": "example-user-id",
        },
    }
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_schemas.py::test_jira_attachment_schema_normalizes_metadata -v
```

Expected: FAIL with `ImportError` or `AttributeError` because `JiraAttachment` does not exist.

- [ ] **Step 3: Implement `JiraAttachment`**

In `src/atlassian_cli/products/jira/schemas.py`, add this class after `JiraComment`:

```python
class JiraAttachment(ApiModel):
    id: str | None = None
    filename: str = ""
    size: int | None = None
    mime_type: str | None = None
    created: str | None = None
    download_url: str | None = None
    author: JiraUser | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any] | None, **kwargs: Any) -> "JiraAttachment":
        data = data or {}
        raw_size = data.get("size")
        try:
            size = int(raw_size) if raw_size is not None else None
        except (TypeError, ValueError):
            size = None
        return cls(
            id=coerce_str(data.get("id")),
            filename=str(data.get("filename", "")),
            size=size,
            mime_type=coerce_str(first_present(data.get("mimeType"), data.get("mime_type"))),
            created=coerce_str(data.get("created")),
            download_url=coerce_str(first_present(data.get("content"), data.get("download_url"))),
            author=JiraUser.from_api_response(data.get("author")) if data.get("author") else None,
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "size": self.size,
            "mime_type": self.mime_type,
            "created": self.created,
            "download_url": self.download_url,
        }
        if self.author:
            payload["author"] = self.author.to_simplified_dict()
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}
```

- [ ] **Step 4: Run the schema test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_schemas.py::test_jira_attachment_schema_normalizes_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/atlassian_cli/products/jira/schemas.py tests/products/jira/test_schemas.py
git commit -m "feat: add jira attachment schema"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 2: Add Jira Provider Attachment Methods

**Files:**
- Modify: `src/atlassian_cli/products/jira/providers/base.py`
- Modify: `src/atlassian_cli/products/jira/providers/server.py`
- Modify: `tests/products/jira/test_provider.py`

- [ ] **Step 1: Write provider tests**

Append these tests to `tests/products/jira/test_provider.py`:

```python
def test_list_issue_attachments_fetches_attachment_field_only() -> None:
    calls = {}

    class FakeClient:
        def issue(self, issue_key: str, fields="*all", expand=None) -> dict:
            calls["args"] = (issue_key, fields, expand)
            return {"fields": {"attachment": [{"id": "10001", "filename": "report.pdf"}]}}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_issue_attachments("DEMO-1")

    assert result == [{"id": "10001", "filename": "report.pdf"}]
    assert calls["args"] == ("DEMO-1", "attachment", None)


def test_upload_issue_attachment_delegates_to_client() -> None:
    calls = {}

    class FakeClient:
        def add_attachment(self, issue_key: str, filename: str) -> dict:
            calls["args"] = (issue_key, filename)
            return {"id": "10001", "filename": "report.pdf", "size": 42}

    provider = build_provider_with_client(FakeClient())

    result = provider.upload_issue_attachment("DEMO-1", "/tmp/report.pdf")

    assert result == {"id": "10001", "filename": "report.pdf", "size": 42}
    assert calls["args"] == ("DEMO-1", "/tmp/report.pdf")


def test_download_issue_attachment_streams_to_destination(tmp_path) -> None:
    calls = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 64 * 1024
            yield b"example "
            yield b"report\n"

    class FakeSession:
        def get(self, url: str, *, stream: bool):
            calls.append((url, stream))
            return FakeResponse()

    class FakeClient:
        _session = FakeSession()

    provider = build_provider_with_client(FakeClient())
    target = tmp_path / "report.pdf"

    result = provider.download_issue_attachment(
        {
            "id": "10001",
            "filename": "report.pdf",
            "content": "attachment://DEMO-1/report.pdf",
        },
        str(target),
        issue_key="DEMO-1",
    )

    assert target.read_bytes() == b"example report\n"
    assert result == {
        "issue_key": "DEMO-1",
        "attachment_id": "10001",
        "filename": "report.pdf",
        "path": str(target),
        "bytes_written": 15,
    }
    assert calls == [
        ("attachment://DEMO-1/report.pdf", True)
    ]
```

- [ ] **Step 2: Run provider tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_provider.py::test_list_issue_attachments_fetches_attachment_field_only tests/products/jira/test_provider.py::test_upload_issue_attachment_delegates_to_client tests/products/jira/test_provider.py::test_download_issue_attachment_streams_to_destination -v
```

Expected: FAIL because provider methods are missing.

- [ ] **Step 3: Extend the Jira provider protocol**

Add these methods to `src/atlassian_cli/products/jira/providers/base.py` after `update_issue`:

```python
    def list_issue_attachments(self, issue_key: str) -> list[dict]: ...
    def upload_issue_attachment(self, issue_key: str, file_path: str) -> dict: ...
    def download_issue_attachment(
        self, attachment: dict, destination: str, *, issue_key: str
    ) -> dict: ...
```

- [ ] **Step 4: Implement the server provider methods**

Add imports at the top of `src/atlassian_cli/products/jira/providers/server.py`:

```python
from pathlib import Path
```

Add these methods after `update_issue`:

```python
    def list_issue_attachments(self, issue_key: str) -> list[dict]:
        issue = self.client.issue(issue_key, fields="attachment")
        fields = issue.get("fields") if isinstance(issue, dict) else {}
        attachments = fields.get("attachment", []) if isinstance(fields, dict) else []
        return [item for item in attachments if isinstance(item, dict)]

    def upload_issue_attachment(self, issue_key: str, file_path: str) -> dict:
        response = self.client.add_attachment(issue_key, file_path)
        return response if isinstance(response, dict) else {"uploaded": bool(response)}

    def download_issue_attachment(
        self, attachment: dict, destination: str, *, issue_key: str
    ) -> dict:
        filename = str(attachment.get("filename") or attachment.get("id") or "attachment")
        download_url = attachment.get("content") or attachment.get("download_url")
        if not isinstance(download_url, str) or not download_url:
            raise RuntimeError(f"attachment download url missing for {filename}")

        target = Path(destination)
        if target.exists() and target.is_dir():
            target = target / Path(filename).name
        elif destination.endswith("/") or destination.endswith("\\"):
            target.mkdir(parents=True, exist_ok=True)
            target = target / Path(filename).name
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        session = getattr(self.client, "_session", None)
        if session is None:
            raise RuntimeError("attachment download is unavailable without an HTTP session")

        bytes_written = 0
        response = session.get(download_url, stream=True)
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                bytes_written += len(chunk)

        return {
            "issue_key": issue_key,
            "attachment_id": str(attachment.get("id", "")),
            "filename": filename,
            "path": str(target),
            "bytes_written": bytes_written,
        }
```

- [ ] **Step 5: Run provider tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_provider.py::test_list_issue_attachments_fetches_attachment_field_only tests/products/jira/test_provider.py::test_upload_issue_attachment_delegates_to_client tests/products/jira/test_provider.py::test_download_issue_attachment_streams_to_destination -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/atlassian_cli/products/jira/providers/base.py src/atlassian_cli/products/jira/providers/server.py tests/products/jira/test_provider.py
git commit -m "feat: add jira attachment provider methods"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 3: Add Jira Attachment Service

**Files:**
- Create: `src/atlassian_cli/products/jira/services/attachment.py`
- Create: `tests/products/jira/test_attachment_service.py`

- [ ] **Step 1: Write service tests**

Create `tests/products/jira/test_attachment_service.py`:

```python
import pytest

from atlassian_cli.products.jira.services.attachment import AttachmentService


class FakeAttachmentProvider:
    def list_issue_attachments(self, issue_key: str) -> list[dict]:
        assert issue_key == "DEMO-1"
        return [
            {
                "id": "10001",
                "filename": "report.pdf",
                "size": 42,
                "mimeType": "application/pdf",
                "content": "attachment://DEMO-1/report.pdf",
            }
        ]

    def upload_issue_attachment(self, issue_key: str, file_path: str) -> dict:
        assert issue_key == "DEMO-1"
        assert file_path == "/tmp/report.pdf"
        return {"id": "10001", "filename": "report.pdf", "size": 42}

    def download_issue_attachment(
        self, attachment: dict, destination: str, *, issue_key: str
    ) -> dict:
        assert attachment["id"] == "10001"
        assert destination == "/tmp/report.pdf"
        assert issue_key == "DEMO-1"
        return {
            "issue_key": "DEMO-1",
            "attachment_id": "10001",
            "filename": "report.pdf",
            "path": "/tmp/report.pdf",
            "bytes_written": 15,
        }


def test_attachment_service_list_normalizes_results() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.list("DEMO-1")

    assert result == {
        "results": [
            {
                "id": "10001",
                "filename": "report.pdf",
                "size": 42,
                "mime_type": "application/pdf",
                "download_url": "attachment://DEMO-1/report.pdf",
            }
        ]
    }


def test_attachment_service_upload_normalizes_result() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.upload("DEMO-1", "/tmp/report.pdf")

    assert result == {"id": "10001", "filename": "report.pdf", "size": 42}


def test_attachment_service_download_by_name() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.download("DEMO-1", name="report.pdf", destination="/tmp/report.pdf")

    assert result["attachment_id"] == "10001"
    assert result["bytes_written"] == 15


def test_attachment_service_download_missing_name_raises_clear_error() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    with pytest.raises(ValueError, match="No attachment named missing.pdf"):
        service.download("DEMO-1", name="missing.pdf", destination="/tmp/missing.pdf")
```

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_attachment_service.py -v
```

Expected: FAIL because `src/atlassian_cli/products/jira/services/attachment.py` does not exist.

- [ ] **Step 3: Implement service**

Create `src/atlassian_cli/products/jira/services/attachment.py`:

```python
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraAttachment


class AttachmentService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def list(self, issue_key: str) -> dict:
        attachments = [
            JiraAttachment.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_issue_attachments(issue_key)
            if isinstance(item, dict)
        ]
        return {"results": attachments}

    def list_raw(self, issue_key: str) -> list[dict]:
        return self.provider.list_issue_attachments(issue_key)

    def upload(self, issue_key: str, file_path: str) -> dict:
        return JiraAttachment.from_api_response(
            self.provider.upload_issue_attachment(issue_key, file_path)
        ).to_simplified_dict()

    def upload_raw(self, issue_key: str, file_path: str) -> dict:
        return self.provider.upload_issue_attachment(issue_key, file_path)

    def download(self, issue_key: str, *, name: str, destination: str) -> dict:
        return self.provider.download_issue_attachment(
            self._resolve_attachment(issue_key, name),
            destination,
            issue_key=issue_key,
        )

    def download_raw(self, issue_key: str, *, name: str, destination: str) -> dict:
        return self.download(issue_key, name=name, destination=destination)

    def _resolve_attachment(self, issue_key: str, name: str) -> dict:
        matches = [
            item
            for item in self.provider.list_issue_attachments(issue_key)
            if isinstance(item, dict) and item.get("filename") == name
        ]
        if not matches:
            raise ValueError(f"No attachment named {name} found on issue {issue_key}")
        if len(matches) > 1:
            raise ValueError(f"Multiple attachments named {name} found on issue {issue_key}")
        return matches[0]
```

- [ ] **Step 4: Run service tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_attachment_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/atlassian_cli/products/jira/services/attachment.py tests/products/jira/test_attachment_service.py
git commit -m "feat: add jira attachment service"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 4: Add Jira Attachment Commands

**Files:**
- Create: `src/atlassian_cli/products/jira/commands/attachment.py`
- Modify: `src/atlassian_cli/products/jira/commands/issue.py`
- Create: `tests/products/jira/test_attachment_command.py`
- Modify: `tests/test_cli_help.py`

- [ ] **Step 1: Write command tests**

Create `tests/products/jira/test_attachment_command.py`:

```python
from typer.testing import CliRunner

from atlassian_cli.cli import app

runner = CliRunner()


def test_jira_issue_attachment_list_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import attachment as attachment_module

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"list": lambda self, issue_key: {"results": [{"filename": "report.pdf"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "attachment",
            "list",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"filename": "report.pdf"' in result.stdout


def test_jira_issue_attachment_upload_uses_positional_file(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import attachment as attachment_module

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "upload": lambda self, issue_key, file_path: {
                    "issue_key": issue_key,
                    "filename": file_path,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "attachment",
            "upload",
            "DEMO-1",
            "./report.pdf",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"issue_key": "DEMO-1"' in result.stdout
    assert '"filename": "./report.pdf"' in result.stdout


def test_jira_issue_attachment_download_outputs_json(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.jira.commands import attachment as attachment_module

    target = tmp_path / "report.pdf"
    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "download": lambda self, issue_key, *, name, destination: {
                    "issue_key": issue_key,
                    "filename": name,
                    "path": destination,
                    "bytes_written": 15,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "jira",
            "issue",
            "attachment",
            "download",
            "DEMO-1",
            "--name",
            "report.pdf",
            "--destination",
            str(target),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"filename": "report.pdf"' in result.stdout
    assert str(target) in result.stdout
```

Append this help test to `tests/test_cli_help.py`:

```python
def test_jira_issue_help_lists_attachment_subcommand() -> None:
    result = runner.invoke(app, ["jira", "issue", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "attachment" in plain_output
```

- [ ] **Step 2: Run command tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_attachment_command.py tests/test_cli_help.py::test_jira_issue_help_lists_attachment_subcommand -v
```

Expected: FAIL because the command module and subcommand are missing.

- [ ] **Step 3: Implement command module**

Create `src/atlassian_cli/products/jira/commands/attachment.py`:

```python
import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.factory import build_provider
from atlassian_cli.products.jira.services.attachment import AttachmentService

app = typer.Typer(help="Jira issue attachment commands")


def build_attachment_service(context) -> AttachmentService:
    return AttachmentService(provider=build_provider(context))


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    issue_key: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = service.list_raw(issue_key) if is_raw_output(output) else service.list(issue_key)
    typer.echo(render_output(payload, output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    issue_key: str,
    file_path: str,
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.upload_raw(issue_key, file_path)
        if is_raw_output(output)
        else service.upload(issue_key, file_path)
    )
    typer.echo(render_output(payload, output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    issue_key: str,
    name: str = typer.Option(..., "--name"),
    destination: str = typer.Option(..., "--destination"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.download_raw(issue_key, name=name, destination=destination)
        if is_raw_output(output)
        else service.download(issue_key, name=name, destination=destination)
    )
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Register nested command**

At the top of `src/atlassian_cli/products/jira/commands/issue.py`, add:

```python
from atlassian_cli.products.jira.commands.attachment import app as attachment_app
```

After `app = typer.Typer(help="Jira issue commands")`, add:

```python
app.add_typer(attachment_app, name="attachment")
```

- [ ] **Step 5: Run command tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/jira/test_attachment_command.py tests/test_cli_help.py::test_jira_issue_help_lists_attachment_subcommand -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/atlassian_cli/products/jira/commands/attachment.py src/atlassian_cli/products/jira/commands/issue.py tests/products/jira/test_attachment_command.py tests/test_cli_help.py
git commit -m "feat: add jira issue attachment commands"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 5: Extend Confluence Attachment Service and Provider

**Files:**
- Modify: `src/atlassian_cli/products/confluence/providers/base.py`
- Modify: `src/atlassian_cli/products/confluence/providers/server.py`
- Modify: `src/atlassian_cli/products/confluence/services/attachment.py`
- Modify: `tests/products/confluence/test_provider.py`
- Modify: `tests/products/confluence/test_attachment_service.py`

- [ ] **Step 1: Write Confluence provider tests**

Append these tests to `tests/products/confluence/test_provider.py`:

```python
def test_list_attachments_forwards_pagination_and_filters() -> None:
    calls = {}

    class FakeClient:
        def get_attachments_from_content(
            self, page_id: str, *, start: int, limit: int, filename: str | None, media_type: str | None
        ):
            calls["args"] = (page_id, start, limit, filename, media_type)
            return {"results": []}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_attachments(
        "1234",
        start=5,
        limit=10,
        filename="diagram.png",
        media_type="image/png",
    )

    assert result == {"results": []}
    assert calls["args"] == ("1234", 5, 10, "diagram.png", "image/png")


def test_upload_attachment_forwards_comment(tmp_path) -> None:
    calls = {}

    class FakeClient:
        def attach_file(self, file_path: str, *, page_id: str, comment: str | None):
            calls["args"] = (file_path, page_id, comment)
            return {"results": [{"id": "55", "title": "diagram.png"}]}

    upload_file = tmp_path / "diagram.png"
    upload_file.write_bytes(b"png")
    provider = build_provider_with_client(FakeClient())

    result = provider.upload_attachment("1234", str(upload_file), comment="example comment")

    assert result == {"id": "55", "title": "diagram.png"}
    assert calls["args"] == (str(upload_file), "1234", "example comment")
```

Append this service test to `tests/products/confluence/test_attachment_service.py`:

```python
def test_attachment_service_download_by_page_and_name() -> None:
    class FakeProvider(FakeAttachmentProvider):
        def download_attachment_from_content(
            self, page_id: str, name: str, destination: str
        ) -> dict:
            assert page_id == "1234"
            assert name == "deploy.log"
            assert destination == "/tmp/deploy.log"
            return {
                "page_id": page_id,
                "attachment_id": "55",
                "title": name,
                "path": destination,
                "bytes_written": 21,
            }

    service = AttachmentService(provider=FakeProvider())

    result = service.download_from_content("1234", name="deploy.log", destination="/tmp/deploy.log")

    assert result["attachment_id"] == "55"
    assert result["bytes_written"] == 21
```

- [ ] **Step 2: Run Confluence tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/confluence/test_provider.py::test_list_attachments_forwards_pagination_and_filters tests/products/confluence/test_provider.py::test_upload_attachment_forwards_comment tests/products/confluence/test_attachment_service.py::test_attachment_service_download_by_page_and_name -v
```

Expected: FAIL because signatures and service method are missing.

- [ ] **Step 3: Extend Confluence provider protocol**

In `src/atlassian_cli/products/confluence/providers/base.py`, replace the attachment method declarations with:

```python
    def list_attachments(
        self,
        page_id: str,
        *,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict: ...
    def upload_attachment(
        self, page_id: str, file_path: str, *, comment: str | None = None
    ) -> dict: ...
    def download_attachment(self, attachment_id: str, destination: str) -> dict: ...
    def download_attachment_from_content(
        self, page_id: str, name: str, destination: str
    ) -> dict: ...
```

- [ ] **Step 4: Extend Confluence server provider**

In `src/atlassian_cli/products/confluence/providers/server.py`, change `list_attachments` and `upload_attachment` to:

```python
    def list_attachments(
        self,
        page_id: str,
        *,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict:
        return self.client.get_attachments_from_content(
            page_id,
            start=start,
            limit=limit,
            filename=filename,
            media_type=media_type,
        )

    def upload_attachment(
        self, page_id: str, file_path: str, *, comment: str | None = None
    ) -> dict:
        response = self.client.attach_file(file_path, page_id=page_id, comment=comment)
        if isinstance(response, dict):
            results = response.get("results")
            if isinstance(results, list) and results and isinstance(results[0], dict):
                return results[0]
        return response
```

Add this method after `download_attachment`:

```python
    def download_attachment_from_content(
        self, page_id: str, name: str, destination: str
    ) -> dict:
        matches = self.list_attachments(page_id, filename=name).get("results", [])
        matches = [
            item
            for item in matches
            if isinstance(item, dict) and item.get("title") == name
        ]
        if not matches:
            raise RuntimeError(f"No attachment named {name} found on page {page_id}")
        if len(matches) > 1:
            raise RuntimeError(f"Multiple attachments named {name} found on page {page_id}")
        result = self.download_attachment(str(matches[0]["id"]), destination)
        result["page_id"] = page_id
        return result
```

- [ ] **Step 5: Extend Confluence service**

In `src/atlassian_cli/products/confluence/services/attachment.py`, update methods to accept options:

```python
    def list(
        self,
        page_id: str,
        *,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict:
        raw = self.provider.list_attachments(
            page_id,
            start=start,
            limit=limit,
            filename=filename,
            media_type=media_type,
        )
```

Also update `list_raw`, `upload`, and `upload_raw` to forward `comment`, then add:

```python
    def download_from_content(self, page_id: str, *, name: str, destination: str) -> dict:
        return self.provider.download_attachment_from_content(page_id, name, destination)

    def download_from_content_raw(
        self, page_id: str, *, name: str, destination: str
    ) -> dict:
        return self.download_from_content(page_id, name=name, destination=destination)
```

- [ ] **Step 6: Run Confluence tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/confluence/test_provider.py::test_list_attachments_forwards_pagination_and_filters tests/products/confluence/test_provider.py::test_upload_attachment_forwards_comment tests/products/confluence/test_attachment_service.py::test_attachment_service_download_by_page_and_name -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/atlassian_cli/products/confluence/providers/base.py src/atlassian_cli/products/confluence/providers/server.py src/atlassian_cli/products/confluence/services/attachment.py tests/products/confluence/test_provider.py tests/products/confluence/test_attachment_service.py
git commit -m "feat: extend confluence attachment service"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 6: Add Confluence Page Attachment Commands

**Files:**
- Create: `src/atlassian_cli/products/confluence/commands/page_attachment.py`
- Modify: `src/atlassian_cli/products/confluence/commands/page.py`
- Modify: `src/atlassian_cli/products/confluence/commands/attachment.py`
- Modify: `tests/products/confluence/test_page_command.py`
- Modify: `tests/products/confluence/test_attachment_command.py`
- Modify: `tests/test_cli_help.py`

- [ ] **Step 1: Write page alias command test**

Append this test to `tests/products/confluence/test_page_command.py`:

```python
def test_confluence_page_attachment_download_outputs_json(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.confluence.commands import page_attachment as attachment_module

    target = tmp_path / "diagram.png"
    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "download_from_content": lambda self, page_id, *, name, destination: {
                    "page_id": page_id,
                    "title": name,
                    "path": destination,
                    "bytes_written": 3,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "confluence",
            "page",
            "attachment",
            "download",
            "1234",
            "--name",
            "diagram.png",
            "--destination",
            str(target),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"page_id": "1234"' in result.stdout
    assert str(target) in result.stdout
```

Append this test to `tests/products/confluence/test_attachment_command.py`:

```python
def test_confluence_attachment_list_accepts_filters(monkeypatch) -> None:
    from atlassian_cli.products.confluence.commands import attachment as attachment_module

    monkeypatch.setattr(
        attachment_module,
        "build_attachment_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "list": lambda self, page_id, **kwargs: {
                    "page_id": page_id,
                    "filters": kwargs,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "DEMO",
            "confluence",
            "attachment",
            "list",
            "1234",
            "--start",
            "5",
            "--limit",
            "10",
            "--filename",
            "diagram.png",
            "--media-type",
            "image/png",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"filename": "diagram.png"' in result.stdout
    assert '"media_type": "image/png"' in result.stdout
```

Append this help test to `tests/test_cli_help.py`:

```python
def test_confluence_page_help_lists_attachment_subcommand() -> None:
    result = runner.invoke(app, ["confluence", "page", "--help"], env=ci_output_env())
    plain_output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "attachment" in plain_output
```

- [ ] **Step 2: Run command tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/products/confluence/test_page_command.py::test_confluence_page_attachment_download_outputs_json tests/products/confluence/test_attachment_command.py::test_confluence_attachment_list_accepts_filters tests/test_cli_help.py::test_confluence_page_help_lists_attachment_subcommand -v
```

Expected: FAIL because page attachment alias and filter options are missing.

- [ ] **Step 3: Create page attachment command module**

Create `src/atlassian_cli/products/confluence/commands/page_attachment.py`:

```python
import typer

from atlassian_cli.output.modes import OutputMode, is_raw_output
from atlassian_cli.output.renderers import render_output
from atlassian_cli.products.confluence.services.attachment import AttachmentService
from atlassian_cli.products.factory import build_provider

app = typer.Typer(help="Confluence page attachment commands")


def build_attachment_service(context) -> AttachmentService:
    return AttachmentService(provider=build_provider(context))


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    page_id: str,
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(50, "--limit"),
    filename: str | None = typer.Option(None, "--filename"),
    media_type: str | None = typer.Option(None, "--media-type"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    kwargs = {
        "start": start,
        "limit": limit,
        "filename": filename,
        "media_type": media_type,
    }
    payload = (
        service.list_raw(page_id, **kwargs)
        if is_raw_output(output)
        else service.list(page_id, **kwargs)
    )
    typer.echo(render_output(payload, output=output))


@app.command("upload")
def upload_attachment(
    ctx: typer.Context,
    page_id: str,
    file_path: str,
    comment: str | None = typer.Option(None, "--comment"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.upload_raw(page_id, file_path, comment=comment)
        if is_raw_output(output)
        else service.upload(page_id, file_path, comment=comment)
    )
    typer.echo(render_output(payload, output=output))


@app.command("download")
def download_attachment(
    ctx: typer.Context,
    page_id: str,
    name: str = typer.Option(..., "--name"),
    destination: str = typer.Option(..., "--destination"),
    output: OutputMode = typer.Option(OutputMode.MARKDOWN, "--output"),
) -> None:
    service = build_attachment_service(ctx.obj)
    payload = (
        service.download_from_content_raw(page_id, name=name, destination=destination)
        if is_raw_output(output)
        else service.download_from_content(page_id, name=name, destination=destination)
    )
    typer.echo(render_output(payload, output=output))
```

- [ ] **Step 4: Register page attachment alias**

In `src/atlassian_cli/products/confluence/commands/page.py`, add:

```python
from atlassian_cli.products.confluence.commands.page_attachment import app as attachment_app
```

After `app = typer.Typer(help="Confluence page commands")`, add:

```python
app.add_typer(attachment_app, name="attachment")
```

- [ ] **Step 5: Add options to the existing top-level command**

In `src/atlassian_cli/products/confluence/commands/attachment.py`, update `list_attachments` and `upload_attachment` signatures to include:

```python
    start: int = typer.Option(0, "--start"),
    limit: int = typer.Option(50, "--limit"),
    filename: str | None = typer.Option(None, "--filename"),
    media_type: str | None = typer.Option(None, "--media-type"),
```

and:

```python
    comment: str | None = typer.Option(None, "--comment"),
```

Forward these options to `service.list*` and `service.upload*`.

- [ ] **Step 6: Run command tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/products/confluence/test_page_command.py::test_confluence_page_attachment_download_outputs_json tests/products/confluence/test_attachment_command.py::test_confluence_attachment_list_accepts_filters tests/test_cli_help.py::test_confluence_page_help_lists_attachment_subcommand -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/atlassian_cli/products/confluence/commands/page_attachment.py src/atlassian_cli/products/confluence/commands/page.py src/atlassian_cli/products/confluence/commands/attachment.py tests/products/confluence/test_page_command.py tests/products/confluence/test_attachment_command.py tests/test_cli_help.py
git commit -m "feat: add confluence page attachment commands"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 7: Update E2E Coverage and README

**Files:**
- Modify: `tests/e2e/coverage_manifest.py`
- Modify: `tests/e2e/test_jira_live.py`
- Modify: `tests/e2e/test_confluence_live.py`
- Modify: `README.md`

- [ ] **Step 1: Update coverage manifest**

Add these entries to `tests/e2e/coverage_manifest.py`:

```python
    "jira issue attachment list": "test_jira_issue_round_trip_live",
    "jira issue attachment upload": "test_jira_issue_round_trip_live",
    "jira issue attachment download": "test_jira_issue_round_trip_live",
    "confluence page attachment list": "test_confluence_attachment_round_trip_live",
    "confluence page attachment upload": "test_confluence_attachment_round_trip_live",
    "confluence page attachment download": "test_confluence_attachment_round_trip_live",
```

- [ ] **Step 2: Extend Jira live e2e**

Inside `test_jira_issue_round_trip_live` in `tests/e2e/test_jira_live.py`, after the comment edit assertions and before cleanup, add:

```python
        attachment_path = Path(live_env.tmp_path if hasattr(live_env, "tmp_path") else ".")
```

If `live_env` has no `tmp_path`, instead change the test function signature to:

```python
def test_jira_issue_round_trip_live(live_env, tmp_path) -> None:
```

and add this block:

```python
        upload_file = tmp_path / "report.pdf"
        upload_file.write_text("example report\n")

        uploaded_attachment = run_json(
            live_env,
            "jira",
            "issue",
            "attachment",
            "upload",
            issue_key,
            str(upload_file),
            "--output",
            "json",
        )
        assert uploaded_attachment["filename"] == "report.pdf"

        listed_attachments = run_json(
            live_env,
            "jira",
            "issue",
            "attachment",
            "list",
            issue_key,
            "--output",
            "json",
        )
        assert any(item["filename"] == "report.pdf" for item in listed_attachments["results"])

        download_target = tmp_path / "downloaded-report.pdf"
        downloaded_attachment = run_json(
            live_env,
            "jira",
            "issue",
            "attachment",
            "download",
            issue_key,
            "--name",
            "report.pdf",
            "--destination",
            str(download_target),
            "--output",
            "json",
        )
        assert Path(downloaded_attachment["path"]).read_text() == "example report\n"
```

Also ensure `from pathlib import Path` is imported at the top of the file.

- [ ] **Step 3: Extend Confluence live e2e**

Inside `test_confluence_attachment_round_trip_live` in `tests/e2e/test_confluence_live.py`, after the existing top-level download assertion, add:

```python
        page_alias_upload = tmp_path / "diagram.png"
        page_alias_upload.write_text("example diagram\n")

        uploaded_via_page = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "upload",
            page_id,
            str(page_alias_upload),
            "--output",
            "json",
        )
        assert uploaded_via_page["title"] == "diagram.png"

        listed_via_page = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "list",
            page_id,
            "--filename",
            "diagram.png",
            "--output",
            "json",
        )
        assert any(item["title"] == "diagram.png" for item in listed_via_page["results"])

        page_download_target = tmp_path / "downloaded-diagram.png"
        downloaded_via_page = run_json(
            live_env,
            "confluence",
            "page",
            "attachment",
            "download",
            page_id,
            "--name",
            "diagram.png",
            "--destination",
            str(page_download_target),
            "--output",
            "json",
        )
        assert Path(downloaded_via_page["path"]).read_text() == "example diagram\n"
```

- [ ] **Step 4: Update README**

In `README.md`, add public-safe examples near the existing Jira and Confluence examples:

```markdown
- `atlassian jira issue attachment list DEMO-1`
- `atlassian jira issue attachment upload DEMO-1 ./report.pdf`
- `atlassian jira issue attachment download DEMO-1 --name report.pdf --destination ./report.pdf`
- `atlassian confluence page attachment list 1234`
- `atlassian confluence page attachment upload 1234 ./diagram.png`
- `atlassian confluence page attachment download 1234 --name diagram.png --destination ./diagram.png`
```

In the feature list, include:

```markdown
- Jira issue attachment upload, list, and download
- Confluence page attachment upload, list, and download
```

- [ ] **Step 5: Run manifest/help/readme tests**

Run:

```bash
.venv/bin/python -m pytest tests/e2e/test_coverage_manifest.py tests/test_readme.py tests/test_cli_help.py -v
```

Expected: PASS.

- [ ] **Step 6: Scan docs/tests/examples for public data violations**

Run:

```bash
rg -n "ACV|PROJ-|@[^ ]+\\.[^ ]+|corp|internal|company" README.md docs tests src
```

Expected: no real-looking sample data introduced by this feature. Existing unrelated matches must be reviewed before committing.

- [ ] **Step 7: Commit**

Run:

```bash
git add README.md tests/e2e/coverage_manifest.py tests/e2e/test_jira_live.py tests/e2e/test_confluence_live.py
git commit -m "docs: document attachment commands"
```

Expected: commit succeeds and does not include `uv.lock`.

### Task 8: Run Final Verification

**Files:**
- Verify: repository working tree and full test suite.

- [ ] **Step 1: Run formatting check**

Run:

```bash
.venv/bin/ruff format --check .
```

Expected: PASS.

- [ ] **Step 2: Run full unit and integration test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run lint check**

Run:

```bash
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: PASS.

- [ ] **Step 4: Run live Jira attachment e2e if environment is available**

Run:

```bash
ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_jira_live.py::test_jira_issue_round_trip_live -q
```

Expected: PASS. If credentials or the live Jira environment are unavailable, record the exact blocker and do not call Jira attachment behavior live-verified.

- [ ] **Step 5: Run live Confluence attachment e2e if environment is available**

Run:

```bash
ATLASSIAN_E2E=1 .venv/bin/python -m pytest tests/e2e/test_confluence_live.py::test_confluence_attachment_round_trip_live -q
```

Expected: PASS. If credentials or the live Confluence environment are unavailable, record the exact blocker and do not call Confluence attachment behavior live-verified.

- [ ] **Step 6: Confirm only intended files changed**

Run:

```bash
git status --short
```

Expected: either clean or only unrelated pre-existing untracked files such as `uv.lock`. Do not add unrelated files.

## Self-Review

- Spec coverage: Tasks 1-4 implement Jira schema/provider/service/commands; Tasks 5-6 implement Confluence option forwarding and page aliases; Task 7 covers README, live e2e, and coverage manifest; Task 8 covers repository verification and live e2e gates.
- Placeholder scan: the plan contains no `TBD`, `TODO`, `implement later`, or unspecified test instructions.
- Type consistency: command names, service method names, provider method names, and output keys are consistent across tasks.
