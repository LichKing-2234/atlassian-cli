import json

import pytest
from requests import HTTPError

from atlassian_cli.config.models import Product
from tests.e2e.support import (
    CleanupRegistry,
    build_jira_create_payload,
    build_live_context,
    discover_jira_comment_visibilities,
    discover_jira_issue_type,
    run_cli,
    unique_name,
)

pytestmark = pytest.mark.e2e


def _stored_comment(provider, issue_key: str, comment_id: str) -> dict | None:
    response = provider.client.issue_get_comments(issue_key)
    comments = response.get("comments", []) if isinstance(response, dict) else []
    return next((item for item in comments if str(item.get("id")) == comment_id), None)


def _add_restricted_comment(
    live_env,
    provider,
    issue_key: str,
    body: str,
    body_format: str,
    candidates: list[dict[str, str]],
) -> dict:
    for visibility in candidates:
        args = [
            "jira",
            "comment",
            "add",
            issue_key,
            "--body",
            body,
            "--visibility",
            json.dumps(visibility),
            "--output",
            "json",
        ]
        if body_format == "jira":
            args.extend(("--body-format", "jira"))
        result = run_cli(live_env, *args)
        if result.returncode != 0:
            continue
        comment_id = str(json.loads(result.stdout)["id"])
        stored = _stored_comment(provider, issue_key, comment_id)
        if stored is not None and stored.get("visibility") == visibility:
            return stored
    raise AssertionError("no readable Jira comment visibility candidate accepted the add request")


def _edit_restricted_comment(
    live_env,
    provider,
    issue_key: str,
    comment_id: str,
    body: str,
    body_format: str,
    candidates: list[dict[str, str]],
) -> dict | None:
    for visibility in candidates:
        args = [
            "jira",
            "comment",
            "edit",
            issue_key,
            comment_id,
            "--body",
            body,
            "--visibility",
            json.dumps(visibility),
            "--output",
            "json",
        ]
        if body_format == "jira":
            args.extend(("--body-format", "jira"))
        result = run_cli(live_env, *args)
        if result.returncode != 0:
            continue
        stored = _stored_comment(provider, issue_key, comment_id)
        if stored is not None and stored.get("visibility") == visibility:
            return stored
    return None


def test_jira_comment_contracts_live(live_env, jira_fixed_version) -> None:
    provider = jira_fixed_version
    jira_context = build_live_context(Product.JIRA, live_env)
    username = jira_context.auth.username
    issue_type = discover_jira_issue_type(
        provider,
        project_key=live_env.jira_project,
        reporter_name=username,
    )
    issue = provider.create_issue(
        build_jira_create_payload(
            provider,
            project_key=live_env.jira_project,
            summary=unique_name("Example issue summary"),
            issue_type=issue_type,
            env_overrides={},
            reporter_name=username,
        )
    )
    issue_key = issue["key"]
    registry = CleanupRegistry()
    registry.add(f"jira issue delete {issue_key}", lambda: provider.delete_issue(issue_key))

    try:
        role_candidates = discover_jira_comment_visibilities(provider, live_env.jira_project)
        user = provider.client.user(username, expand="groups") if username else {}
        group_page = user.get("groups", {}) if isinstance(user, dict) else {}
        group_items = group_page.get("items") or group_page.get("values") or []
        group_candidates = [
            {"type": "group", "value": item["name"]}
            for item in group_items
            if isinstance(item, dict) and item.get("name")
        ]
        assert group_candidates, "authenticated user has no discoverable Jira groups"

        jira_added = _add_restricted_comment(
            live_env,
            provider,
            issue_key,
            "h2. Example Page\n\n{code}example response{code}",
            "jira",
            role_candidates,
        )
        assert jira_added["body"] == "h2. Example Page\n\n{code}example response{code}"

        jira_edited = _edit_restricted_comment(
            live_env,
            provider,
            issue_key,
            str(jira_added["id"]),
            "h3. Example Page\n\n{{example response}}",
            "jira",
            group_candidates,
        )
        group_visibility_enabled = jira_edited is not None
        if jira_edited is None:
            with pytest.raises(HTTPError) as captured:
                provider.edit_comment(
                    issue_key,
                    str(jira_added["id"]),
                    "h3. Example Page\n\n{{example response}}",
                    group_candidates[0],
                )
            response = captured.value.response
            assert response is not None and response.status_code == 400
            error_payload = response.json()
            assert "commentLevel" in error_payload.get("errors", {})
            jira_edited = _edit_restricted_comment(
                live_env,
                provider,
                issue_key,
                str(jira_added["id"]),
                "h3. Example Page\n\n{{example response}}",
                "jira",
                role_candidates,
            )
        assert jira_edited is not None
        assert jira_edited["body"] == "h3. Example Page\n\n{{example response}}"

        markdown_added = _add_restricted_comment(
            live_env,
            provider,
            issue_key,
            "## Example Page\n\n**example response**",
            "markdown",
            role_candidates,
        )
        assert markdown_added["body"] == "h2. Example Page\n\n*example response*"

        markdown_edited = _edit_restricted_comment(
            live_env,
            provider,
            issue_key,
            str(markdown_added["id"]),
            "### Example Page\n\n`example response`",
            "markdown",
            group_candidates if group_visibility_enabled else role_candidates,
        )
        assert markdown_edited is not None
        assert markdown_edited["body"] == "h3. Example Page\n\n{{example response}}"
    finally:
        registry.run()
