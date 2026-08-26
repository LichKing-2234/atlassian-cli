import json
from pathlib import Path

import pytest

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
        pytest.skip("no Jira field with allowedValues was discoverable for TEST Task")

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


def test_jira_issue_round_trip_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    summary = unique_name("jira-e2e")
    issue_key = None
    try:
        jira_context = build_live_context(Product.JIRA, live_env)
        provider = build_live_provider(Product.JIRA, live_env)
        issue_type = live_env.jira_issue_type or "Task"
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


def test_jira_issue_reparent_subtask_live(live_env) -> None:
    registry = CleanupRegistry()
    jira_context = build_live_context(Product.JIRA, live_env)
    provider = build_live_provider(Product.JIRA, live_env)
    server_info = provider.client.get_server_info()
    assert str(server_info.get("version")) == "7.11.0"
    assert str(server_info.get("buildNumber")) == "711000"
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


def test_jira_issue_batch_create_live(live_env, tmp_path) -> None:
    registry = CleanupRegistry()
    jira_context = build_live_context(Product.JIRA, live_env)
    provider = build_live_provider(Product.JIRA, live_env)
    issue_type = live_env.jira_issue_type or "Task"
    payload = [
        build_jira_create_payload(
            provider,
            project_key=live_env.jira_project,
            summary=unique_name("jira-batch-one"),
            issue_type=issue_type,
            env_overrides={},
            reporter_name=jira_context.auth.username,
        ),
        build_jira_create_payload(
            provider,
            project_key=live_env.jira_project,
            summary=unique_name("jira-batch-two"),
            issue_type=issue_type,
            env_overrides={},
            reporter_name=jira_context.auth.username,
        ),
    ]
    try:
        result = run_json(
            live_env,
            "jira",
            "issue",
            "batch-create",
            "--issues",
            json.dumps(payload),
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


def test_jira_issue_link_round_trip_live(live_env) -> None:
    registry = CleanupRegistry()
    jira_context = build_live_context(Product.JIRA, live_env)
    provider = build_live_provider(Product.JIRA, live_env)
    server_info = provider.client.get_server_info()
    assert server_info["version"] == "7.11.0"
    assert str(server_info["buildNumber"]) == "711000"
    assert server_info["deploymentType"] == "Server"
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
