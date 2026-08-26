import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from requests import HTTPError

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    build_jira_create_payload,
    build_live_context,
    build_live_provider,
    discover_jira_comment_visibilities,
    discover_jira_issue_type,
    run_cli,
    run_failure,
    run_json,
    unique_name,
)

pytestmark = pytest.mark.e2e


def _jira_additional_fields(payload: dict) -> dict:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"project", "issuetype", "summary", "description"}
    }


def _discover_jira_reparent_target(provider, *, reporter_name: str | None):
    issue_types = provider.client.get("rest/api/2/issuetype")
    subtask_ids = {str(item.get("id")) for item in issue_types if item.get("subtask") is True}
    for project in provider.list_projects():
        project_key = project.get("key")
        if not project_key:
            continue
        try:
            meta = provider.client.issue_createmeta(
                project_key, expand="projects.issuetypes.fields"
            )
        except Exception:
            continue
        projects = meta.get("projects", []) if isinstance(meta, dict) else []
        available = projects[0].get("issuetypes", []) if projects else []
        parents = [item for item in available if str(item.get("id")) not in subtask_ids]
        subtasks = [item for item in available if str(item.get("id")) in subtask_ids]
        for parent_type in parents:
            for subtask_type in subtasks:
                try:
                    build_jira_create_payload(
                        provider,
                        project_key=project_key,
                        summary="Example issue summary",
                        issue_type=parent_type["name"],
                        env_overrides={},
                        reporter_name=reporter_name,
                    )
                    build_jira_create_payload(
                        provider,
                        project_key=project_key,
                        summary="Example issue summary",
                        issue_type=subtask_type["name"],
                        env_overrides={"parent": json.dumps({"key": "DEMO-1"})},
                        reporter_name=reporter_name,
                    )
                except RuntimeError:
                    continue
                return project_key, parent_type["name"], subtask_type["name"]
    raise RuntimeError("no writable Jira project with parent and sub-task issue types")


def test_jira_project_and_metadata_live(live_env, jira_fixed_version) -> None:
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

    fields = run_json(
        live_env,
        "jira",
        "field",
        "search",
        "--limit",
        "2",
        "--output",
        "json",
    )
    assert 0 < len(fields["results"]) <= 2
    keyword = fields["results"][0]["name"]
    matching_fields = run_json(
        live_env,
        "jira",
        "field",
        "search",
        "--keyword",
        keyword,
        "--limit",
        "1",
        "--output",
        "json",
    )
    assert len(matching_fields["results"]) == 1
    assert keyword.casefold() in matching_fields["results"][0]["name"].casefold()

    meta = jira_fixed_version.client.issue_createmeta(
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
        pytest.skip("no Jira field with allowedValues was discoverable for TEST Task")

    allowed_values = selected_issue_type["fields"][option_field_id]["allowedValues"]
    option_text = next(
        str(item.get("value") or item.get("name"))
        for item in allowed_values
        if item.get("value") or item.get("name")
    )
    option_result = run_json(
        live_env,
        "jira",
        "field",
        "options",
        option_field_id,
        "--project-key",
        live_env.jira_project,
        "--issue-type",
        str(selected_issue_type["name"]),
        "--contains",
        option_text,
        "--return-limit",
        "1",
        "--output",
        "json",
    )

    assert len(option_result["results"]) == 1
    returned_option = option_result["results"][0]
    returned_text = str(returned_option.get("value") or returned_option.get("name"))
    assert option_text.casefold() in returned_text.casefold()

    jira_context = build_live_context(Product.JIRA, live_env)
    user_query = jira_context.auth.username or "."
    users = run_json(
        live_env,
        "jira",
        "user",
        "search",
        "--query",
        user_query,
        "--project-key",
        live_env.jira_project,
        "--limit",
        "5",
        "--output",
        "raw-json",
    )
    assert 0 < len(users) <= 5
    user_name = next((item.get("name") for item in users if item.get("name")), None)
    if user_name is None:
        pytest.skip("no Jira user with a name field was discoverable")

    existing = jira_fixed_version.search_issues(
        f'project = "{live_env.jira_project}"', fields="key", limit=1
    ).get("issues", [])
    assert existing
    issue_scoped_users = run_json(
        live_env,
        "jira",
        "user",
        "search",
        "--query",
        user_query,
        "--issue-key",
        existing[0]["key"],
        "--limit",
        "1",
        "--output",
        "raw-json",
    )
    assert isinstance(issue_scoped_users, list)
    assert len(issue_scoped_users) <= 1

    user = run_json(live_env, "jira", "user", "get", user_name, "--output", "json")
    assert user["name"] == user_name


def test_jira_issue_round_trip_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    summary = unique_name("jira-e2e")
    issue_key = None
    try:
        jira_context = build_live_context(Product.JIRA, live_env)
        provider = build_live_provider(Product.JIRA, live_env)
        issue_type = live_env.jira_issue_type or discover_jira_issue_type(
            provider,
            project_key=live_env.jira_project,
            reporter_name=jira_context.auth.username,
        )
        payload = build_jira_create_payload(
            provider,
            project_key=live_env.jira_project,
            summary=summary,
            issue_type=issue_type,
            env_overrides={},
            reporter_name=jira_context.auth.username,
        )
        payload["description"] = "created by live e2e"
        created = run_json(
            live_env,
            "jira",
            "issue",
            "create",
            "--project-key",
            live_env.jira_project,
            "--issue-type",
            issue_type,
            "--summary",
            summary,
            "--description",
            "created by live e2e",
            "--additional-fields",
            json.dumps(_jira_additional_fields(payload)),
            "--output",
            "json",
        )
        issue_key = created["issue"]["key"]
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
            "--fields",
            json.dumps(
                {
                    "summary": updated_summary,
                    "description": "updated by live e2e",
                }
            ),
            "--output",
            "json",
        )
        assert updated["issue"]["key"] == issue_key

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

        upload_file = tmp_path / "report.pdf"
        upload_file.write_text("example report\n")
        uploaded = run_json(
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
        assert uploaded["filename"] == "report.pdf"

        listed = run_json(
            live_env,
            "jira",
            "issue",
            "attachment",
            "list",
            issue_key,
            "--output",
            "json",
        )
        assert any(item["filename"] == "report.pdf" for item in listed["results"])

        download_target = tmp_path / "downloaded-report.pdf"
        downloaded = run_json(
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
        assert Path(downloaded["path"]).read_text() == "example report\n"
    finally:
        registry.run()


def test_jira_issue_read_and_attachment_update_live(
    live_env, tmp_path, jira_fixed_version, cleanup_registry
) -> None:
    jira_context = build_live_context(Product.JIRA, live_env)
    issue_type = live_env.jira_issue_type or discover_jira_issue_type(
        jira_fixed_version,
        project_key=live_env.jira_project,
        reporter_name=jira_context.auth.username,
    )
    summary = unique_name("jira-read-update")
    payload = build_jira_create_payload(
        jira_fixed_version,
        project_key=live_env.jira_project,
        summary=summary,
        issue_type=issue_type,
        env_overrides={},
        reporter_name=jira_context.auth.username,
    )
    created = run_json(
        live_env,
        "jira",
        "issue",
        "create",
        "--project-key",
        live_env.jira_project,
        "--issue-type",
        issue_type,
        "--summary",
        summary,
        "--additional-fields",
        json.dumps(_jira_additional_fields(payload)),
        "--output",
        "json",
    )
    issue_key = created["issue"]["key"]
    cleanup_registry.add(
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

    jira_fixed_version.client.set_issue_property(
        issue_key, "example-property", {"value": "example response"}
    )
    run_json(
        live_env,
        "jira",
        "comment",
        "add",
        issue_key,
        "--body",
        "example comment",
        "--output",
        "json",
    )
    latest_comment = run_json(
        live_env,
        "jira",
        "comment",
        "add",
        issue_key,
        "--body",
        "example response",
        "--output",
        "json",
    )

    fetched = run_json(
        live_env,
        "jira",
        "issue",
        "get",
        issue_key,
        "--fields",
        "summary",
        "--comment-limit",
        "1",
        "--properties",
        "example-property",
        "--update-history",
        "false",
        "--output",
        "raw-json",
    )
    assert fetched["key"] == issue_key
    assert [item["id"] for item in fetched["fields"]["comment"]["comments"]] == [
        latest_comment["id"]
    ]
    assert fetched["properties"]["example-property"] == {"value": "example response"}

    attachment_path = tmp_path / "report.pdf"
    attachment_path.write_text("example response\n")
    updated = run_json(
        live_env,
        "jira",
        "issue",
        "update",
        issue_key,
        "--fields",
        json.dumps({"summary": f"{summary}-updated"}),
        "--attachments",
        json.dumps([str(attachment_path)]),
        "--output",
        "json",
    )
    assert updated["issue"]["key"] == issue_key

    listed = run_json(
        live_env,
        "jira",
        "issue",
        "attachment",
        "list",
        issue_key,
        "--output",
        "json",
    )
    assert any(item["filename"] == "report.pdf" for item in listed["results"])


def test_jira_issue_reparent_subtask_live(live_env, jira_fixed_version) -> None:
    registry = CleanupRegistry()
    jira_context = build_live_context(Product.JIRA, live_env)
    provider = jira_fixed_version
    project_key, parent_type, subtask_type = _discover_jira_reparent_target(
        provider, reporter_name=jira_context.auth.username
    )
    marker = unique_name("jira-reparent-e2e")
    try:
        parent_keys = []
        for index in (1, 2):
            payload = build_jira_create_payload(
                provider,
                project_key=project_key,
                summary=f"{marker}-parent-{index}",
                issue_type=parent_type,
                env_overrides={},
                reporter_name=jira_context.auth.username,
            )
            parent_key = provider.create_issue(payload)["key"]
            parent_keys.append(parent_key)
            registry.add(
                f"jira issue delete {parent_key}",
                lambda key=parent_key: provider.delete_issue(key),
            )

        child_payload = build_jira_create_payload(
            provider,
            project_key=project_key,
            summary=f"{marker}-child",
            issue_type=subtask_type,
            env_overrides={"parent": json.dumps({"key": parent_keys[0]})},
            reporter_name=jira_context.auth.username,
        )
        child_key = provider.create_issue(child_payload)["key"]
        registry.add(
            f"jira issue delete {child_key}",
            lambda: provider.delete_issue(child_key),
        )

        moved = run_json(
            live_env,
            "jira",
            "issue",
            "reparent-subtask",
            child_key,
            "--parent",
            parent_keys[1],
            "--output",
            "json",
        )
        assert moved == {
            "issue_key": child_key,
            "previous_parent": parent_keys[0],
            "new_parent": parent_keys[1],
        }

        moved_back = run_json(
            live_env,
            "jira",
            "issue",
            "reparent-subtask",
            child_key,
            "--parent",
            parent_keys[0],
            "--output",
            "raw-json",
        )
        assert moved_back["previous_parent"] == parent_keys[1]
        assert moved_back["new_parent"] == parent_keys[0]
    finally:
        registry.run()


def test_jira_issue_create_and_batch_contracts_live(
    live_env, jira_fixed_version, cleanup_registry
) -> None:
    jira_context = build_live_context(Product.JIRA, live_env)
    assert jira_context.auth.username is not None
    issue_type = live_env.jira_issue_type or discover_jira_issue_type(
        jira_fixed_version,
        project_key=live_env.jira_project,
        reporter_name=jira_context.auth.username,
    )
    components = jira_fixed_version.client.get(
        f"rest/api/2/project/{live_env.jira_project}/components"
    )
    component_name = next(
        (item.get("name") for item in components if isinstance(item, dict) and item.get("name")),
        None,
    )
    assert component_name is not None

    def required_fields(summary: str) -> dict:
        payload = build_jira_create_payload(
            jira_fixed_version,
            project_key=live_env.jira_project,
            summary=summary,
            issue_type=issue_type,
            env_overrides={},
            reporter_name=jira_context.auth.username,
        )
        additional = _jira_additional_fields(payload)
        additional.pop("assignee", None)
        additional.pop("components", None)
        return additional

    def register_cleanup(issue_key: str) -> None:
        cleanup_registry.add(
            f"jira issue delete {issue_key}",
            lambda key=issue_key: run_json(
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

    def read_fields(issue_key: str) -> dict:
        return run_json(
            live_env,
            "jira",
            "issue",
            "get",
            issue_key,
            "--fields",
            "summary,description,assignee,components",
            "--comment-limit",
            "0",
            "--output",
            "raw-json",
        )["fields"]

    markdown_summary = unique_name("jira-create-markdown")
    markdown_description = "## Example Page\n\n- example response"
    created = run_json(
        live_env,
        "jira",
        "issue",
        "create",
        "--project-key",
        live_env.jira_project,
        "--issue-type",
        issue_type,
        "--summary",
        markdown_summary,
        "--assignee",
        jira_context.auth.username,
        "--description",
        markdown_description,
        "--components",
        component_name,
        "--additional-fields",
        json.dumps(required_fields(markdown_summary)),
        "--output",
        "json",
    )
    markdown_key = created["issue"]["key"]
    register_cleanup(markdown_key)
    markdown_fields = read_fields(markdown_key)
    assert markdown_fields["summary"] == markdown_summary
    assert markdown_fields["description"] == "h2. Example Page\n\n* example response"
    assert markdown_fields["assignee"]["name"] == jira_context.auth.username
    assert component_name in [item["name"] for item in markdown_fields["components"]]

    jira_summary = unique_name("jira-create-markup")
    jira_description = "h2. Example Page\n\n* example response"
    created = run_json(
        live_env,
        "jira",
        "issue",
        "create",
        "--project-key",
        live_env.jira_project,
        "--issue-type",
        issue_type,
        "--summary",
        jira_summary,
        "--description",
        jira_description,
        "--description-format",
        "jira",
        "--additional-fields",
        json.dumps(required_fields(jira_summary)),
        "--output",
        "json",
    )
    jira_key = created["issue"]["key"]
    register_cleanup(jira_key)
    assert read_fields(jira_key)["description"] == jira_description

    batch_summaries = [unique_name("jira-batch-one"), unique_name("jira-batch-two")]
    batch_issues = [
        {
            **required_fields(batch_summaries[0]),
            "project_key": live_env.jira_project,
            "summary": batch_summaries[0],
            "issue_type": issue_type,
            "description": markdown_description,
            "assignee": jira_context.auth.username,
            "components": [component_name],
        },
        {
            **required_fields(batch_summaries[1]),
            "project_key": live_env.jira_project,
            "summary": batch_summaries[1],
            "issue_type": issue_type,
            "description": jira_description,
            "description_format": "jira",
        },
    ]
    result = run_json(
        live_env,
        "jira",
        "issue",
        "batch-create",
        "--issues",
        json.dumps(batch_issues),
        "--output",
        "json",
    )
    batch_keys = [item["key"] for item in result["issues"]]
    assert len(batch_keys) == 2
    for issue_key in batch_keys:
        register_cleanup(issue_key)
    first_fields = read_fields(batch_keys[0])
    second_fields = read_fields(batch_keys[1])
    assert first_fields["summary"] == batch_summaries[0]
    assert first_fields["description"] == "h2. Example Page\n\n* example response"
    assert first_fields["assignee"]["name"] == jira_context.auth.username
    assert component_name in [item["name"] for item in first_fields["components"]]
    assert second_fields["summary"] == batch_summaries[1]
    assert second_fields["description"] == jira_description

    validation_summary = unique_name("jira-batch-validate")
    validated = run_json(
        live_env,
        "jira",
        "issue",
        "batch-create",
        "--issues",
        json.dumps(
            [
                {
                    **required_fields(validation_summary),
                    "project_key": live_env.jira_project,
                    "summary": validation_summary,
                    "issue_type": issue_type,
                    "description": markdown_description,
                }
            ]
        ),
        "--validate-only",
        "--output",
        "json",
    )
    assert validated == {"message": "Issues validated successfully", "issues": []}
    search = jira_fixed_version.search_issues(
        f'project = {live_env.jira_project} AND summary ~ "{validation_summary}"',
        start=0,
        limit=10,
    )
    assert search["issues"] == []


def test_jira_issue_update_assignment_transition_contracts_live(
    live_env, jira_fixed_version, cleanup_registry, tmp_path
) -> None:
    jira_context = build_live_context(Product.JIRA, live_env)
    assert jira_context.auth.username is not None
    issue_type = live_env.jira_issue_type or discover_jira_issue_type(
        jira_fixed_version,
        project_key=live_env.jira_project,
        reporter_name=jira_context.auth.username,
    )
    summary = unique_name("jira-update-contract")
    payload = build_jira_create_payload(
        jira_fixed_version,
        project_key=live_env.jira_project,
        summary=summary,
        issue_type=issue_type,
        env_overrides={},
        reporter_name=jira_context.auth.username,
    )
    payload.pop("assignee", None)
    created = run_json(
        live_env,
        "jira",
        "issue",
        "create",
        "--project-key",
        live_env.jira_project,
        "--issue-type",
        issue_type,
        "--summary",
        summary,
        "--additional-fields",
        json.dumps(_jira_additional_fields(payload)),
        "--output",
        "json",
    )
    issue_key = created["issue"]["key"]
    cleanup_registry.add(
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

    assigned = run_json(
        live_env,
        "jira",
        "issue",
        "assign",
        issue_key,
        "--assignee",
        jira_context.auth.username,
        "--output",
        "json",
    )
    assert assigned["issue"]["assignee"]["name"] == jira_context.auth.username
    unassigned = run_json(live_env, "jira", "issue", "assign", issue_key, "--output", "json")
    assert unassigned["issue"]["assignee"]["name"] == "Unassigned"

    transitions = jira_fixed_version.get_issue_transitions(issue_key)
    assert transitions
    transition = transitions[0]
    visibility = None
    for candidate in discover_jira_comment_visibilities(jira_fixed_version, live_env.jira_project):
        try:
            probe = jira_fixed_version.add_comment(issue_key, "example response", candidate)
        except HTTPError:
            continue
        if probe.get("visibility") == candidate:
            visibility = candidate
            break
    assert visibility is not None
    attachment_path = tmp_path / "report.pdf"
    attachment_path.write_bytes(b"example response\n")
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000%z")
    updated_summary = f"{summary}-updated"
    updated = run_json(
        live_env,
        "jira",
        "issue",
        "update",
        issue_key,
        "--fields",
        json.dumps(
            {
                "summary": updated_summary,
                "description": "## Example Update",
            }
        ),
        "--attachments",
        json.dumps([str(attachment_path)]),
        "--transition",
        str(transition["id"]),
        "--comment",
        "## Example Comment",
        "--comment-visibility",
        json.dumps(visibility),
        "--worklog",
        "1m",
        "--worklog-started",
        started,
        "--output",
        "json",
    )
    assert updated["operations_performed"] == [
        "fields_updated",
        "attachments_uploaded",
        f"transitioned:{transition['id']}",
        "comment_added",
        "worklog_added",
    ]

    readback = jira_fixed_version.get_issue(
        issue_key, fields="summary,description,status,attachment"
    )["fields"]
    assert readback["summary"] == updated_summary
    assert readback["description"] == "h2. Example Update"
    assert any(item["filename"] == "report.pdf" for item in readback["attachment"])
    assert readback["status"]["name"] == transition["to"]

    comments = jira_fixed_version.client.issue_get_comments(issue_key)["comments"]
    update_comment = next(item for item in comments if item["body"] == "h2. Example Comment")
    assert update_comment["visibility"] == visibility
    worklogs = jira_fixed_version.client.issue_get_worklog(issue_key)["worklogs"]
    assert any(item.get("timeSpentSeconds") == 60 for item in worklogs)

    next_transitions = jira_fixed_version.get_issue_transitions(issue_key)
    assert next_transitions
    transitioned = run_json(
        live_env,
        "jira",
        "issue",
        "transition",
        issue_key,
        "--transition-id",
        str(next_transitions[0]["id"]),
        "--fields",
        "{}",
        "--comment",
        "**example transition**",
        "--output",
        "json",
    )
    assert transitioned["issue"]["key"] == issue_key
    comments = jira_fixed_version.client.issue_get_comments(issue_key)["comments"]
    assert any(item["body"] == "*example transition*" for item in comments)


def test_jira_issue_link_round_trip_live(live_env, jira_fixed_version) -> None:
    registry = CleanupRegistry()
    jira_context = build_live_context(Product.JIRA, live_env)
    provider = jira_fixed_version
    issue_type = live_env.jira_issue_type or discover_jira_issue_type(
        provider,
        project_key=live_env.jira_project,
        reporter_name=jira_context.auth.username,
    )

    def create_issue(prefix: str) -> str:
        payload = build_jira_create_payload(
            provider,
            project_key=live_env.jira_project,
            summary=unique_name(prefix),
            issue_type=issue_type,
            env_overrides={},
            reporter_name=jira_context.auth.username,
        )
        created = run_json(
            live_env,
            "jira",
            "issue",
            "create",
            "--project-key",
            live_env.jira_project,
            "--issue-type",
            issue_type,
            "--summary",
            payload["summary"],
            "--additional-fields",
            json.dumps(_jira_additional_fields(payload)),
            "--output",
            "json",
        )
        issue_key = created["issue"]["key"]
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
        return issue_key

    link_id: str | None = None

    def cleanup_link() -> None:
        if link_id is not None:
            run_json(
                live_env,
                "jira",
                "issue",
                "link",
                "delete",
                link_id,
                "--yes",
                "--output",
                "json",
            )

    try:
        inward_issue = create_issue("Example issue summary")
        outward_issue = create_issue("Example issue summary")
        link_types = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "types",
            "--output",
            "json",
        )
        link_type = next(
            (item["name"] for item in link_types["results"] if item.get("name")),
            None,
        )
        assert link_type is not None
        filtered_types = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "types",
            "--name-filter",
            link_type,
            "--output",
            "json",
        )
        assert any(item.get("name") == link_type for item in filtered_types["results"])
        created = None
        visibility = None
        for candidate in discover_jira_comment_visibilities(provider, live_env.jira_project):
            result = run_cli(
                live_env,
                "jira",
                "issue",
                "link",
                "create",
                "--inward",
                inward_issue,
                "--outward",
                outward_issue,
                "--type",
                link_type,
                "--comment",
                "example comment",
                "--comment-visibility",
                json.dumps(candidate),
                "--output",
                "json",
            )
            if result.returncode == 0:
                created = json.loads(result.stdout)
                visibility = candidate
                break
            failed_links = provider.list_issue_links(inward_issue)
            for failed_link in failed_links:
                provider.delete_issue_link(str(failed_link["id"]))
            assert provider.list_issue_links(inward_issue) == []
        assert created is not None
        assert visibility is not None
        assert created["status"] == "created"
        assert created["created"] is True
        assert created["link"]["inward_issue"] == inward_issue
        assert created["link"]["outward_issue"] == outward_issue
        link_id = created["link"]["id"]
        registry.add("jira issue link delete", cleanup_link)
        comments = []
        for issue_key in (inward_issue, outward_issue):
            issue = provider.get_issue(issue_key, fields="comment")
            comment_page = issue.get("fields", {}).get("comment", {})
            comments.extend(comment_page.get("comments", []))
        created_comment = next(
            (item for item in comments if item.get("body") == "example comment"),
            None,
        )
        assert created_comment is not None
        assert created_comment.get("visibility") == visibility

        duplicate = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "create",
            "--inward",
            inward_issue,
            "--outward",
            outward_issue,
            "--type",
            link_type,
            "--output",
            "json",
        )
        assert duplicate["status"] == "existing"
        assert duplicate["created"] is False
        assert duplicate["link"]["id"] == link_id

        inward_links = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "list",
            inward_issue,
            "--output",
            "json",
        )
        outward_links = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "list",
            outward_issue,
            "--output",
            "json",
        )
        assert any(
            item["id"] == link_id and item["direction"] == "outward"
            for item in inward_links["results"]
        )
        assert any(
            item["id"] == link_id and item["direction"] == "inward"
            for item in outward_links["results"]
        )

        deleted = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "delete",
            link_id,
            "--yes",
            "--output",
            "json",
        )
        assert deleted == {"id": link_id, "deleted": True}
        link_id = None
        remaining = run_json(
            live_env,
            "jira",
            "issue",
            "link",
            "list",
            inward_issue,
            "--output",
            "json",
        )
        assert all(item["id"] != deleted["id"] for item in remaining["results"])
    finally:
        registry.run()


def test_jira_issue_changelog_batch_rejected_live(live_env) -> None:
    output = run_failure(
        live_env,
        "jira",
        "issue",
        "changelog-batch",
        "--issue",
        "DEMO-1",
        expected="Cloud support is not available in v1",
    )
    assert "Cloud support is not available in v1" in output
