from atlassian import Jira
from requests import HTTPError

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

    def get_issue(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        unsupported_options: list[str] = []
        if comment_limit != 10:
            unsupported_options.append("comment_limit")
        if properties:
            unsupported_options.append("properties")
        if update_history is not True:
            unsupported_options.append("update_history")
        if unsupported_options:
            raise NotImplementedError(
                "Jira Server/DC provider does not support get_issue options: "
                + ", ".join(unsupported_options)
            )
        return self.client.issue(issue_key, fields=fields or "*all", expand=expand)

    def search_issues(
        self,
        jql: str,
        start: int = 0,
        limit: int = 25,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        start_at: int | None = None,
        projects_filter: list[str] | None = None,
    ) -> dict:
        scoped_jql = jql
        if projects_filter:
            project_clause = ", ".join(projects_filter)
            scoped_jql = f"project in ({project_clause}) AND ({jql})"
        resolved_start = start if start_at is None else start_at
        if fields is None and expand is None:
            return self.client.jql(scoped_jql, start=resolved_start, limit=limit)
        return self.client.jql(
            scoped_jql,
            fields=fields or "*all",
            start=resolved_start,
            limit=limit,
            expand=expand,
        )

    def create_issue(self, fields: dict) -> dict:
        return self.client.issue_create(fields=fields)

    def create_issues(self, issues: list[dict]) -> list[dict]:
        try:
            return self.client.create_issues(issues)
        except HTTPError as exc:
            response = getattr(exc, "response", None)
            if response is None or response.status_code < 500:
                raise
            return [self.client.issue_create(fields=issue) for issue in issues]

    def update_issue(self, issue_key: str, fields: dict) -> dict:
        self.client.issue_update(issue_key, fields=fields)
        return {"key": issue_key, "updated": True}

    def get_create_meta(self, project_key: str, issue_type: str) -> dict:
        meta = self.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
        projects = meta.get("projects", []) if isinstance(meta, dict) else []
        issue_types = projects[0].get("issuetypes", []) if projects else []
        selected = next(
            (
                item
                for item in issue_types
                if item.get("name") == issue_type or str(item.get("id")) == issue_type
            ),
            None,
        )
        if selected is None:
            return {"required": [], "allowed_values": {}}
        fields = selected.get("fields", {})
        return {
            "required": [
                field_id
                for field_id, info in fields.items()
                if isinstance(info, dict) and info.get("required")
            ],
            "allowed_values": {
                field_id: info.get("allowedValues", [])
                for field_id, info in fields.items()
                if isinstance(info, dict) and info.get("allowedValues")
            },
        }

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
        meta = self.client.issue_createmeta(project_key, expand="projects.issuetypes.fields")
        projects = meta.get("projects", [])
        if not projects:
            return []
        issue_types = projects[0].get("issuetypes", [])
        if not issue_types:
            return []
        issue_type_meta = next(
            (
                item
                for item in issue_types
                if item.get("name") == issue_type or str(item.get("id")) == issue_type
            ),
            None,
        )
        if issue_type_meta is None:
            return []
        fields = issue_type_meta.get("fields", {})
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
