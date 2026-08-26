import json
import re

import pytest
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


def test_jira_issue_watcher_list_routes_issue_key(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, str] = {}

    class FakeService:
        def get_watchers(self, issue_key: str) -> dict:
            captured["issue_key"] = issue_key
            return {
                "issue_key": issue_key,
                "watcher_count": 1,
                "is_watching": True,
                "watchers": [{"name": "example-user-id"}],
            }

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
            "watcher",
            "list",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {"issue_key": "DEMO-1"}
    assert json.loads(result.stdout)["watchers"] == [{"name": "example-user-id"}]


def test_jira_issue_watcher_add_routes_server_user_identifier(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, str] = {}

    class FakeService:
        def add_watcher(self, issue_key: str, user_identifier: str) -> dict:
            captured.update(issue_key=issue_key, user_identifier=user_identifier)
            return {
                "success": True,
                "issue_key": issue_key,
                "user": user_identifier,
            }

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
            "watcher",
            "add",
            "DEMO-1",
            "--user-identifier",
            "example-user-id",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "issue_key": "DEMO-1",
        "user_identifier": "example-user-id",
    }


def test_jira_issue_watcher_remove_routes_server_username(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, str] = {}

    class FakeService:
        def remove_watcher(self, issue_key: str, username: str) -> dict:
            captured.update(issue_key=issue_key, username=username)
            return {"success": True, "issue_key": issue_key, "user": username}

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
            "watcher",
            "remove",
            "DEMO-1",
            "--username",
            "example-user-id",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {"issue_key": "DEMO-1", "username": "example-user-id"}


def test_jira_issue_worklog_list_routes_issue_key(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, str] = {}

    class FakeService:
        def get_worklogs(self, issue_key: str) -> dict:
            captured["issue_key"] = issue_key
            return {"worklogs": [{"id": "10001", "time_spent_seconds": 60}]}

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
            "worklog",
            "list",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {"issue_key": "DEMO-1"}
    assert json.loads(result.stdout)["worklogs"][0]["time_spent_seconds"] == 60


def test_jira_issue_worklog_add_routes_all_semantic_inputs(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def add_worklog(self, issue_key: str, time_spent: str, **kwargs) -> dict:
            captured.update(issue_key=issue_key, time_spent=time_spent, **kwargs)
            return {
                "message": "Worklog added successfully",
                "worklog": {"id": "10001", "time_spent_seconds": 60},
            }

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
            "worklog",
            "add",
            "DEMO-1",
            "--time-spent",
            "1m",
            "--comment",
            "**example comment**",
            "--started",
            "2026-08-26T10:00:00.000+0000",
            "--original-estimate",
            "1h",
            "--remaining-estimate",
            "30m",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "issue_key": "DEMO-1",
        "time_spent": "1m",
        "comment": "**example comment**",
        "comment_format": "markdown",
        "started": "2026-08-26T10:00:00.000+0000",
        "original_estimate": "1h",
        "remaining_estimate": "30m",
    }


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


def test_jira_issue_transition_accepts_fields_and_comment(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured = {}

    class FakeService:
        def transition(self, issue_key, transition, **kwargs):
            captured["args"] = (issue_key, transition, kwargs)
            return {"message": "Issue transitioned successfully", "issue": {"key": issue_key}}

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
            "transition",
            "DEMO-1",
            "--transition-id",
            "Done",
            "--fields",
            '{"resolution":{"name":"Fixed"}}',
            "--comment",
            "h2. Example Page",
            "--comment-format",
            "jira",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["args"] == (
        "DEMO-1",
        "Done",
        {
            "fields": {"resolution": {"name": "Fixed"}},
            "comment": "h2. Example Page",
            "comment_format": "jira",
        },
    )


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


@pytest.mark.parametrize("comment_limit", ["-1", "101"])
def test_jira_issue_get_rejects_comment_limit_outside_upstream_range(
    monkeypatch, comment_limit: str
) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    class FakeService:
        def get(self, issue_key, **kwargs):
            raise AssertionError(f"service should not be called for {issue_key}: {kwargs}")

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
            "--comment-limit",
            comment_limit,
        ],
    )

    assert result.exit_code != 0
    assert "0" in result.output
    assert "100" in result.output


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


def test_jira_issue_create_accepts_jira_markup_description_format(monkeypatch) -> None:
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
            "--description",
            "h2. Requirements",
            "--description-format",
            "jira",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["description_format"] == "jira"


def test_jira_issue_create_raw_keeps_semantic_description_contract(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def create_raw(self, **kwargs):
            captured.update(kwargs)
            return {"key": "DEMO-2"}

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
            "--description",
            "# Requirements",
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert captured["description"] == "# Requirements"
    assert captured["description_format"] == "markdown"


def test_jira_issue_update_accepts_optional_aligned_operations(monkeypatch) -> None:
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
            "--additional-fields",
            '{"labels":["ops"]}',
            "--components",
            "API",
            "--attachments",
            '["release.txt"]',
            "--transition",
            "31",
            "--comment",
            "h2. Example Page",
            "--comment-format",
            "jira",
            "--comment-visibility",
            '{"type":"role","value":"reviewer-one"}',
            "--worklog",
            "1m",
            "--worklog-started",
            "2026-08-26T10:00:00.000+0000",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "issue_key": "DEMO-1",
        "kwargs": {
            "fields": {},
            "additional_fields": {"labels": ["ops"]},
            "components": ["API"],
            "attachments": ["release.txt"],
            "transition": "31",
            "comment": "h2. Example Page",
            "comment_format": "jira",
            "comment_visibility": {"type": "role", "value": "reviewer-one"},
            "worklog": "1m",
            "worklog_started": "2026-08-26T10:00:00.000+0000",
            "description_format": "markdown",
        },
    }


def test_jira_issue_update_raw_routes_attachments_separately(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def update_raw(self, issue_key, **kwargs):
            captured["issue_key"] = issue_key
            captured["kwargs"] = kwargs
            return {"key": issue_key, "updated": True}

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
            "--attachments",
            '["release.txt"]',
            "--output",
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "issue_key": "DEMO-1",
        "kwargs": {
            "fields": {"summary": "Updated summary"},
            "additional_fields": {},
            "components": None,
            "attachments": ["release.txt"],
            "transition": None,
            "comment": None,
            "comment_format": "markdown",
            "comment_visibility": None,
            "worklog": None,
            "worklog_started": None,
            "description_format": "markdown",
        },
    }


@pytest.mark.parametrize(
    ("assignee_args", "expected"),
    [(["--assignee", "example-user"], "example-user"), ([], None)],
)
def test_jira_issue_assign_supports_assignment_and_unassignment(
    monkeypatch, assignee_args, expected
) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured = {}

    class FakeService:
        def assign(self, issue_key, assignee):
            captured["args"] = (issue_key, assignee)
            return {"message": "Issue assigned successfully", "issue": {"key": issue_key}}

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
            "assign",
            "DEMO-1",
            *assignee_args,
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["args"] == ("DEMO-1", expected)


def test_jira_issue_reparent_subtask_outputs_json(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured = {}

    class FakeService:
        def reparent_subtask(self, issue_key: str, parent_key: str) -> dict:
            captured["args"] = (issue_key, parent_key)
            return {
                "issue_key": issue_key,
                "previous_parent": "DEMO-2",
                "new_parent": parent_key,
            }

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
            "reparent-subtask",
            "DEMO-1234",
            "--parent",
            "DEMO-1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["args"] == ("DEMO-1234", "DEMO-1")
    assert json.loads(result.stdout) == {
        "issue_key": "DEMO-1234",
        "previous_parent": "DEMO-2",
        "new_parent": "DEMO-1",
    }


def test_jira_issue_batch_create_accepts_semantic_issues_and_validate_only(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def batch_create(self, issues, *, validate_only: bool):
            captured["issues"] = issues
            captured["validate_only"] = validate_only
            return {"message": "Issues validated successfully", "issues": []}

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
    assert captured == {
        "issues": [
            {
                "project_key": "DEMO",
                "summary": "Example issue summary",
                "issue_type": "Task",
            }
        ],
        "validate_only": True,
    }


def test_jira_issue_batch_create_raw_preserves_validate_only(monkeypatch) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    captured: dict[str, object] = {}

    class FakeService:
        def batch_create_raw(self, issues, *, validate_only: bool):
            captured["issues"] = issues
            captured["validate_only"] = validate_only
            return []

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
            "raw-json",
        ],
    )

    assert result.exit_code == 0
    assert captured["validate_only"] is True


def test_jira_issue_batch_create_reads_json_file(monkeypatch, tmp_path) -> None:
    from atlassian_cli.products.jira.commands import issue as issue_module

    file_path = tmp_path / "issues.json"
    file_path.write_text(
        json.dumps(
            [
                {
                    "project_key": "DEMO",
                    "issue_type": "Task",
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
            {
                "batch_create": lambda self, issues, *, validate_only: {
                    "issues": [{"key": "DEMO-1"}]
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
