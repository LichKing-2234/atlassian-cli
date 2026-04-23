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

    def update_issue(self, issue_key: str, fields: dict) -> dict:
        self.client.issue_update(issue_key, fields=fields)
        return {"key": issue_key, "updated": True}

    def transition_issue(self, issue_key: str, transition: str) -> dict:
        self.client.set_issue_status(issue_key, transition)
        return {"key": issue_key, "transition": transition}

    def list_projects(self) -> list[dict]:
        return self.client.projects()

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def get_user(self, username: str) -> dict:
        return self.client.user(username)

    def search_users(self, query: str) -> list[dict]:
        return self.client.user_find_by_user_string(query)
