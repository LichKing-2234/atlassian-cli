from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraIssue, JiraSearchResult


class IssueService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        raw = self.provider.get_issue(
            issue_key,
            fields=fields,
            expand=expand,
            comment_limit=comment_limit,
            properties=properties,
            update_history=update_history,
        )
        return JiraIssue.from_api_response(raw).to_simplified_dict()

    def get_raw(
        self,
        issue_key: str,
        *,
        fields: str | list[str] | None = None,
        expand: str | None = None,
        comment_limit: int = 10,
        properties: list[str] | None = None,
        update_history: bool = True,
    ) -> dict:
        return self.provider.get_issue(
            issue_key,
            fields=fields,
            expand=expand,
            comment_limit=comment_limit,
            properties=properties,
            update_history=update_history,
        )

    def search(
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
        raw = self.provider.search_issues(
            jql,
            fields=fields,
            expand=expand,
            start_at=start if start_at is None else start_at,
            limit=limit,
            projects_filter=projects_filter,
        )
        return JiraSearchResult.from_api_response(raw).to_simplified_dict()

    def search_page(self, jql: str, start: int, limit: int) -> CollectionPage:
        payload = self.search(jql, start, limit)
        return CollectionPage(
            items=payload["issues"],
            start=payload["start_at"],
            limit=payload["max_results"],
            total=payload["total"],
        )

    def search_raw(
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
        return self.provider.search_issues(
            jql,
            fields=fields,
            expand=expand,
            start_at=start if start_at is None else start_at,
            limit=limit,
            projects_filter=projects_filter,
        )

    def create(
        self,
        fields: dict | None = None,
        *,
        project_key: str | None = None,
        summary: str | None = None,
        issue_type: str | None = None,
        assignee: str | None = None,
        description: str | None = None,
        components: list[str] | None = None,
        additional_fields: dict | None = None,
    ) -> dict:
        if fields is None:
            additional_fields = additional_fields or {}
            if project_key is None or summary is None or issue_type is None:
                raise ValueError("project_key, summary, and issue_type are required")
            meta = self.provider.get_create_meta(project_key, issue_type)
            ignored_required = {"project", "issuetype", "summary", "description"}
            missing = [
                field
                for field in meta.get("required", [])
                if field not in ignored_required and field not in additional_fields
            ]
            if missing:
                raise ValueError(f"missing required Jira fields: {', '.join(sorted(missing))}")
            fields = {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
            }
            if assignee:
                fields["assignee"] = {"name": assignee}
            if description:
                fields["description"] = description
            if components:
                fields["components"] = [{"name": name} for name in components]
            fields.update(additional_fields)

        raw = self.provider.create_issue(fields)
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            issue = JiraIssue.from_api_response(raw).to_simplified_dict()
        elif isinstance(raw, dict) and "key" in raw:
            issue = {"key": raw["key"]}
        else:
            issue = raw
        return {"message": "Issue created successfully", "issue": issue}

    def create_raw(self, fields: dict) -> dict:
        return self.provider.create_issue(fields)

    def batch_create(self, issues: list[dict]) -> dict:
        return {
            "issues": [
                JiraIssue.from_api_response(item).to_simplified_dict()
                if isinstance(item, dict) and "fields" in item and "key" in item
                else {"key": item["key"]}
                if isinstance(item, dict) and "key" in item
                else item
                for item in self.provider.create_issues(issues)
            ]
        }

    def batch_create_raw(self, issues: list[dict]) -> list[dict]:
        return self.provider.create_issues(issues)

    def update(
        self,
        issue_key: str,
        fields: dict,
        *,
        additional_fields: dict | None = None,
        components: list[str] | None = None,
        attachments: list[str] | None = None,
    ) -> dict:
        payload = {**fields, **(additional_fields or {})}
        if components:
            payload["components"] = [{"name": name} for name in components]
        if attachments:
            payload["attachments"] = attachments
        raw = self.provider.update_issue(issue_key, payload)
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            issue = JiraIssue.from_api_response(raw).to_simplified_dict()
        else:
            issue = {"key": issue_key, **raw} if isinstance(raw, dict) else {"key": issue_key}
        if isinstance(raw, dict) and raw.get("attachment_results"):
            issue["attachment_results"] = raw["attachment_results"]
        return {"message": "Issue updated successfully", "issue": issue}

    def update_raw(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def transition(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)

    def transition_raw(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)

    def get_transitions(self, issue_key: str) -> dict:
        return {"results": self.provider.get_issue_transitions(issue_key)}

    def get_transitions_raw(self, issue_key: str) -> list[dict]:
        return self.provider.get_issue_transitions(issue_key)

    def delete(self, issue_key: str) -> dict:
        self.provider.delete_issue(issue_key)
        return {"key": issue_key, "deleted": True}

    def delete_raw(self, issue_key: str) -> dict:
        self.provider.delete_issue(issue_key)
        return {"key": issue_key, "deleted": True}
