import json

import pytest

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    build_live_provider,
    run_failure,
    run_json,
    unique_name,
)

pytestmark = pytest.mark.e2e


def test_jira_project_and_metadata_live(live_env) -> None:
    projects = run_json(live_env, "jira", "project", "list", "--output", "json")
    assert any(item["key"] == live_env.jira_project for item in projects["results"])

    project = run_json(
        live_env,
        "jira",
        "project",
        "get",
        live_env.jira_project,
        "--output",
        "json",
    )
    assert project["key"] == live_env.jira_project

    fields = run_json(live_env, "jira", "field", "search", "--query", "", "--output", "json")
    assert fields["results"]

    provider = build_live_provider(Product.JIRA, live_env)
    meta = provider.client.issue_createmeta(
        live_env.jira_project,
        expand="projects.issuetypes.fields",
    )
    projects = meta.get("projects", [])
    issue_types = projects[0].get("issuetypes", []) if projects else []
    selected_issue_type = None
    option_field_id = None
    for issue_type_meta in issue_types:
        fields_meta = issue_type_meta.get("fields", {})
        option_field_id = next(
            (
                field_id
                for field_id, info in fields_meta.items()
                if field_id not in {"issuetype", "project"}
                and isinstance(info, dict)
                and info.get("allowedValues")
            ),
            None,
        )
        if option_field_id is not None:
            selected_issue_type = issue_type_meta
            break
    if option_field_id is None or selected_issue_type is None:
        pytest.skip("no Jira field with allowedValues was discoverable for EEP Task")

    option_result = run_json(
        live_env,
        "jira",
        "field",
        "options",
        option_field_id,
        "--project",
        live_env.jira_project,
        "--issue-type",
        str(selected_issue_type["name"]),
        "--output",
        "json",
    )

    assert option_result["results"]

    users = run_json(live_env, "jira", "user", "search", "--query", "a", "--output", "raw-json")
    user_name = next((item.get("name") for item in users if item.get("name")), None)
    if user_name is None:
        pytest.skip("no Jira user with a name field was discoverable")

    user = run_json(live_env, "jira", "user", "get", user_name, "--output", "json")
    assert user["name"] == user_name


def test_jira_issue_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    summary = unique_name("jira-e2e")
    issue_key = None
    try:
        created = run_json(
            live_env,
            "jira",
            "issue",
            "create",
            "--project",
            live_env.jira_project,
            "--issue-type",
            "Task",
            "--summary",
            summary,
            "--description",
            "created by live e2e",
            "--output",
            "json",
        )
        issue_key = created["key"]
        registry.add(
            f"jira issue delete {issue_key}",
            lambda: run_json(
                live_env,
                "jira",
                "issue",
                "delete",
                issue_key,
                "--yes",
                "--output",
                "json",
            ),
        )

        fetched = run_json(live_env, "jira", "issue", "get", issue_key, "--output", "json")
        assert fetched["key"] == issue_key

        updated_summary = f"{summary}-updated"
        updated = run_json(
            live_env,
            "jira",
            "issue",
            "update",
            issue_key,
            "--summary",
            updated_summary,
            "--description",
            "updated by live e2e",
            "--output",
            "json",
        )
        assert updated["updated"] is True

        search = run_json(
            live_env,
            "jira",
            "issue",
            "search",
            "--jql",
            f'project = {live_env.jira_project} AND summary ~ "{updated_summary}"',
            "--output",
            "json",
        )
        assert any(item["key"] == issue_key for item in search["issues"])

        transitions = run_json(
            live_env,
            "jira",
            "issue",
            "transitions",
            issue_key,
            "--output",
            "json",
        )
        assert transitions["results"]
        transition_name = next(
            (item.get("name") for item in transitions["results"] if item.get("name")),
            None,
        )
        if transition_name is not None:
            transitioned = run_json(
                live_env,
                "jira",
                "issue",
                "transition",
                issue_key,
                "--to",
                transition_name,
                "--output",
                "json",
            )
            assert transitioned["transition"] == transition_name

        comment = run_json(
            live_env,
            "jira",
            "comment",
            "add",
            issue_key,
            "--body",
            "first comment",
            "--output",
            "json",
        )
        assert comment["id"]

        edited = run_json(
            live_env,
            "jira",
            "comment",
            "edit",
            issue_key,
            comment["id"],
            "--body",
            "edited comment",
            "--output",
            "json",
        )
        assert edited["id"] == comment["id"]
    finally:
        registry.run()


def test_jira_issue_batch_create_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    payload = [
        {
            "project": {"key": live_env.jira_project},
            "issuetype": {"name": "Task"},
            "summary": unique_name("jira-batch-one"),
        },
        {
            "project": {"key": live_env.jira_project},
            "issuetype": {"name": "Task"},
            "summary": unique_name("jira-batch-two"),
        },
    ]
    batch_file = tmp_path / "issues.json"
    batch_file.write_text(json.dumps(payload))
    try:
        result = run_json(
            live_env,
            "jira",
            "issue",
            "batch-create",
            "--file",
            str(batch_file),
            "--output",
            "json",
        )
        keys = [item["key"] for item in result["issues"] if item.get("key")]
        assert len(keys) == 2
        for key in keys:
            registry.add(
                f"jira issue delete {key}",
                lambda key=key: run_json(
                    live_env,
                    "jira",
                    "issue",
                    "delete",
                    key,
                    "--yes",
                    "--output",
                    "json",
                ),
            )
    finally:
        registry.run()


def test_jira_issue_changelog_batch_rejected_live(live_env) -> None:
    output = run_failure(
        live_env,
        "jira",
        "issue",
        "changelog-batch",
        "--issue",
        "EEP-1",
        expected="Cloud support is not available in v1",
    )
    assert "Cloud support is not available in v1" in output
