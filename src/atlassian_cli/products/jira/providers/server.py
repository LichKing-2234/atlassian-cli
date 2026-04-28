from atlassian import Jira

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.auth.session_patch import patch_session_headers


class JiraServerProvider:
    def __init__(
        self,
        *,
        auth_mode: AuthMode = AuthMode.BASIC,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if auth_mode in {AuthMode.PAT, AuthMode.BEARER} and token is not None:
            kwargs["token"] = token
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Jira(**kwargs)
        session = getattr(self.client, "_session", None)
        if session is not None:
            patch_session_headers(session, headers or {})

    def get_issue(self, issue_key: str) -> dict:
        return self.client.issue(issue_key)

    def search_issues(self, jql: str, start: int, limit: int) -> dict:
        return self.client.jql(jql, start=start, limit=limit)

    def create_issue(self, fields: dict) -> dict:
        return self.client.issue_create(fields=fields)

    def create_issues(self, issues: list[dict]) -> list[dict]:
        return self.client.create_issues(issues)

    def update_issue(self, issue_key: str, fields: dict) -> dict:
        self.client.issue_update(issue_key, fields=fields)
        return {"key": issue_key, "updated": True}

    def delete_issue(self, issue_key: str) -> None:
        self.client.delete_issue(issue_key)

    def transition_issue(self, issue_key: str, transition: str) -> dict:
        self.client.set_issue_status(issue_key, transition)
        return {"key": issue_key, "transition": transition}

    def get_issue_transitions(self, issue_key: str) -> list[dict]:
        return self.client.get_issue_transitions(issue_key)

    def search_fields(self, query: str) -> list[dict]:
        fields = self.client.get_all_fields()
        query_lower = query.lower()
        return [
            field
            for field in fields
            if not query or query_lower in str(field.get("name", "")).lower()
        ]

    def get_field_options(self, field_id: str, project_key: str, issue_type: str) -> list[dict]:
        meta = self.client.issue_createmeta(project_key, issue_type)
        projects = meta.get("projects", [])
        if not projects:
            return []
        issue_types = projects[0].get("issuetypes", [])
        if not issue_types:
            return []
        fields = issue_types[0].get("fields", {})
        field_meta = fields.get(field_id, {})
        return field_meta.get("allowedValues", [])

    def add_comment(self, issue_key: str, body: str) -> dict:
        return self.client.issue_add_comment(issue_key, body)

    def edit_comment(self, issue_key: str, comment_id: str, body: str) -> dict:
        return self.client.issue_edit_comment(issue_key, comment_id, body)

    def list_projects(self) -> list[dict]:
        return self.client.projects()

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def get_user(self, username: str) -> dict:
        return self.client.user(username)

    def search_users(self, query: str) -> list[dict]:
        return self.client.user_find_by_user_string(query)
