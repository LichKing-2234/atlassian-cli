import json
import re

from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.output.interactive import CollectionPage

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def test_jira_issue_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "summary": "Example issue summary"}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "get", "DEMO-1", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"key": "DEMO-1"' in result.stdout


def test_jira_issue_search_uses_interactive_browser_for_markdown_tty(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    calls: dict[str, object] = {}

    monkeypatch.setattr(issue_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        issue_module, "browse_collection", lambda source: calls.setdefault("source", source)
    )
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
                "get": lambda self, issue_key: {
                    "key": issue_key,
                    "summary": "Example issue summary",
                },
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

    monkeypatch.setattr(
        issue_module, "should_use_interactive_output", lambda *args, **kwargs: False
    )
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


def test_jira_issue_search_interactive_source_uses_generic_preview_renderer(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    sample_issue = {
        "key": "DEMO-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Example Author"},
        "description": "Investigate rollout health",
    }
    captured: dict[str, str] = {}

    class FakeService:
        def search_page(self, jql, start, limit):
            return CollectionPage(items=[sample_issue], start=start, limit=limit, total=1)

        def get(self, issue_key):
            return sample_issue

    monkeypatch.setattr(
        issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService()
    )
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
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = DEMO"],
    )

    assert result.exit_code == 0
    assert captured["item"] == "DEMO-1  Open  Example Author  Example issue summary"
    assert "Status: Open" in captured["preview"]
    assert "Assignee: Example Author" in captured["preview"]


def test_jira_issue_search_falls_back_to_markdown_when_interactive_import_fails(
    monkeypatch,
) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(issue_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        issue_module, "browse_collection", lambda source: (_ for _ in ()).throw(ImportError("boom"))
    )
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
                "get": lambda self, issue_key: {
                    "key": issue_key,
                    "summary": "Example issue summary",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = DEMO"],
    )

    assert result.exit_code == 0
    assert "1. DEMO-1 - Example issue summary" in result.stdout


def test_jira_issue_search_falls_back_to_markdown_when_interactive_runtime_fails(
    monkeypatch,
) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(issue_module, "should_use_interactive_output", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        issue_module,
        "browse_collection",
        lambda source: (_ for _ in ()).throw(RuntimeError("boom")),
    )
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
                "get": lambda self, issue_key: {
                    "key": issue_key,
                    "summary": "Example issue summary",
                },
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = DEMO"],
    )

    assert result.exit_code == 0
    assert "1. DEMO-1 - Example issue summary" in result.stdout


def test_jira_issue_transitions_outputs_available_ids(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {
                "get_transitions": lambda self, issue_key: {
                    "results": [{"id": "31", "name": "Done"}]
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "transitions",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "31"' in result.stdout


def test_jira_issue_delete_requires_confirmation(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"delete": lambda self, issue_key: {"key": issue_key, "deleted": True}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "delete", "DEMO-1"],
    )

    assert result.exit_code != 0
    stripped_output = ANSI_ESCAPE_RE.sub("", result.output)
    normalized_output = " ".join(
        token for token in stripped_output.split() if token.strip("│╭╮╰╯─")
    )
    assert "pass --yes to confirm delete" in normalized_output


def test_jira_issue_delete_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"delete": lambda self, issue_key: {"key": issue_key, "deleted": True}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "delete",
            "DEMO-1",
            "--yes",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"deleted": true' in result.stdout


def test_jira_issue_get_passes_fields_expand_and_comment_limit(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def get(self, issue_key, **kwargs):
            captured["issue_key"] = issue_key
            captured["kwargs"] = kwargs
            return {"key": issue_key, "summary": "Example issue summary"}

    monkeypatch.setattr(
        issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService()
    )

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

    monkeypatch.setattr(
        issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService()
    )

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

    monkeypatch.setattr(
        issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService()
    )

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

    monkeypatch.setattr(
        issue_module, "build_issue_service", lambda *_args, **_kwargs: FakeService()
    )

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


def test_jira_issue_batch_create_reads_json_file(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    file_path = tmp_path / "issues.json"
    file_path.write_text(
        json.dumps(
            [
                {
                    "project": {"key": "DEMO"},
                    "issuetype": {"name": "Task"},
                    "summary": "First issue",
                }
            ]
        )
    )

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"batch_create": lambda self, issues: {"issues": [{"key": "DEMO-1"}]}},
        )(),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "batch-create",
            "--file",
            str(file_path),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"key": "DEMO-1"' in result.stdout


def test_jira_issue_batch_create_rejects_missing_file(tmp_path) -> None:
    missing = tmp_path / "missing.json"

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "batch-create",
            "--file",
            str(missing),
        ],
    )

    assert result.exit_code != 0
    assert "file not found" in result.output


def test_jira_issue_batch_create_rejects_invalid_json(tmp_path) -> None:
    file_path = tmp_path / "issues.json"
    file_path.write_text("{not-json")

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "batch-create",
            "--file",
            str(file_path),
        ],
    )

    assert result.exit_code != 0
    assert "invalid JSON" in result.output


def test_jira_issue_batch_create_requires_array_input(tmp_path) -> None:
    file_path = tmp_path / "issues.json"
    file_path.write_text(json.dumps({"summary": "not-a-list"}))

    result = runner.invoke(
        app,
        [
            "--url",
            "https://jira.example.com",
            "jira",
            "issue",
            "batch-create",
            "--file",
            str(file_path),
        ],
    )

    assert result.exit_code != 0
    assert "JSON array" in result.output


def test_jira_issue_changelog_batch_is_explicitly_unsupported_on_server() -> None:
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
            "DEMO-1",
        ],
    )

    assert result.exit_code != 0
    assert "Cloud support is not available in v1" in result.output
