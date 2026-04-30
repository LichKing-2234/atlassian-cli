import json

from tests.e2e.support.env import LiveEnv


def build_jira_create_payload(
    provider,
    *,
    project_key: str,
    summary: str,
    issue_type: str,
    env_overrides: dict[str, str],
    reporter_name: str | None = None,
) -> dict:
    meta = provider.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
    projects = meta.get("projects", []) if isinstance(meta, dict) else []
    issue_types = projects[0].get("issuetypes", []) if projects else []
    selected = next((item for item in issue_types if item.get("name") == issue_type), None)
    if selected is None:
        available_issue_types = sorted(item.get("name") for item in issue_types if item.get("name"))
        available_display = ", ".join(available_issue_types) if available_issue_types else "none"
        raise RuntimeError(
            "requested Jira issue type "
            f"{issue_type!r} is not available for project {project_key!r}. "
            f"Available issue types: {available_display}. "
            "Set ATLASSIAN_E2E_JIRA_ISSUE_TYPE to one of the available issue types."
        )
    payload = {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    for field_id, info in selected.get("fields", {}).items():
        if field_id in {"project", "issuetype", "summary", "description"}:
            continue
        if not info.get("required"):
            continue
        if field_id in env_overrides:
            payload[field_id] = json.loads(env_overrides[field_id])
            continue
        if field_id == "reporter" and reporter_name:
            payload[field_id] = {"name": reporter_name}
            continue
        allowed = info.get("allowedValues") or []
        if allowed:
            chosen = allowed[0]
            payload[field_id] = {"id": chosen["id"]} if chosen.get("id") else chosen
            continue
        raise RuntimeError(f"missing required test value for {field_id}")
    return payload


def resolve_confluence_write_target(live_env: LiveEnv) -> dict[str, str | None]:
    return {
        "space_key": live_env.confluence_space,
        "parent_page_id": live_env.confluence_parent_page,
    }


def resolve_bitbucket_repo_target(live_env: LiveEnv) -> dict[str, str]:
    return {
        "project_key": live_env.bitbucket_project,
        "repo_slug": live_env.bitbucket_existing_repo or live_env.bitbucket_repo,
    }
