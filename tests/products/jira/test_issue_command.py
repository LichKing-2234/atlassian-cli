from typer.testing import CliRunner
import json

from atlassian_cli.cli import app
from atlassian_cli.output.interactive import CollectionPage

runner = CliRunner()


def test_jira_issue_get_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    monkeypatch.setattr(
        issue_module,
        "build_issue_service",
        lambda *_args, **_kwargs: type(
            "FakeService",
            (),
            {"get": lambda self, issue_key: {"key": issue_key, "summary": "Broken deploy"}},
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "get", "OPS-1", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"key": "OPS-1"' in result.stdout


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
                    "issues": [{"key": "OPS-1", "summary": "Broken deploy"}],
                    "start_at": start,
                    "max_results": limit,
                    "total": 1,
                },
                "search_page": lambda self, jql, start, limit: CollectionPage(
                    items=[{"key": "OPS-1", "summary": "Broken deploy"}],
                    start=start,
                    limit=limit,
                    total=1,
                ),
                "get": lambda self, issue_key: {"key": issue_key, "summary": "Broken deploy"},
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = OPS"],
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
                    "issues": [{"key": "OPS-1", "summary": "Broken deploy"}],
                    "start_at": start,
                    "max_results": limit,
                    "total": 1,
                }
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = OPS"],
    )

    assert result.exit_code == 0
    assert "1. OPS-1 - Broken deploy" in result.stdout


def test_jira_issue_search_interactive_source_uses_generic_preview_renderer(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    sample_issue = {
        "key": "OPS-1",
        "summary": "Broken deploy",
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
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = OPS"],
    )

    assert result.exit_code == 0
    assert captured["item"] == "OPS-1  Open  Alice  Broken deploy"
    assert "Status: Open" in captured["preview"]
    assert "Assignee: Alice" in captured["preview"]


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
                    "issues": [{"key": "OPS-1", "summary": "Broken deploy"}],
                    "start_at": start,
                    "max_results": limit,
                    "total": 1,
                },
                "search_page": lambda self, jql, start, limit: CollectionPage(
                    items=[{"key": "OPS-1", "summary": "Broken deploy"}],
                    start=start,
                    limit=limit,
                    total=1,
                ),
                "get": lambda self, issue_key: {"key": issue_key, "summary": "Broken deploy"},
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = OPS"],
    )

    assert result.exit_code == 0
    assert "1. OPS-1 - Broken deploy" in result.stdout


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
                    "issues": [{"key": "OPS-1", "summary": "Broken deploy"}],
                    "start_at": start,
                    "max_results": limit,
                    "total": 1,
                },
                "search_page": lambda self, jql, start, limit: CollectionPage(
                    items=[{"key": "OPS-1", "summary": "Broken deploy"}],
                    start=start,
                    limit=limit,
                    total=1,
                ),
                "get": lambda self, issue_key: {"key": issue_key, "summary": "Broken deploy"},
            },
        )(),
    )

    result = runner.invoke(
        app,
        ["--url", "https://jira.example.com", "jira", "issue", "search", "--jql", "project = OPS"],
    )

    assert result.exit_code == 0
    assert "1. OPS-1 - Broken deploy" in result.stdout


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
            "OPS-1",
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
        ["--url", "https://jira.example.com", "jira", "issue", "delete", "OPS-1"],
    )

    assert result.exit_code != 0
    assert "pass --yes to confirm delete" in result.output


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
            "OPS-1",
            "--yes",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"deleted": true' in result.stdout


def test_jira_issue_batch_create_reads_json_file(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    file_path = tmp_path / "issues.json"
    file_path.write_text(
        json.dumps(
            [
                {
                    "project": {"key": "OPS"},
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
            {"batch_create": lambda self, issues: {"issues": [{"key": "OPS-1"}]}},
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
    assert '"key": "OPS-1"' in result.stdout
