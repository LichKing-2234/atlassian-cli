from atlassian_cli.products.jira.schemas import JiraFieldName, JiraIssue, JiraPerson


class IssueService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def _normalize_issue(self, raw: dict) -> dict:
        fields = raw["fields"]
        issue = JiraIssue(
            key=raw["key"],
            summary=fields["summary"],
            status=JiraFieldName(name=fields["status"]["name"]),
            assignee=(
                JiraPerson(display_name=fields["assignee"]["displayName"])
                if fields.get("assignee")
                else None
            ),
            reporter=(
                JiraPerson(display_name=fields["reporter"]["displayName"])
                if fields.get("reporter")
                else None
            ),
            priority=(
                JiraFieldName(name=fields["priority"]["name"])
                if fields.get("priority")
                else None
            ),
            updated=fields.get("updated"),
        )
        return issue.model_dump(exclude_none=True)

    def get(self, issue_key: str) -> dict:
        raw = self.provider.get_issue(issue_key)
        return self._normalize_issue(raw)

    def get_raw(self, issue_key: str) -> dict:
        return self.provider.get_issue(issue_key)

    def search(self, jql: str, start: int, limit: int) -> list[dict]:
        return [self._normalize_issue(item) for item in self.provider.search_issues(jql, start, limit)]

    def search_raw(self, jql: str, start: int, limit: int) -> list[dict]:
        return self.provider.search_issues(jql, start, limit)

    def create(self, fields: dict) -> dict:
        raw = self.provider.create_issue(fields)
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            return self._normalize_issue(raw)
        if isinstance(raw, dict) and "key" in raw:
            return {"key": raw["key"]}
        return raw

    def create_raw(self, fields: dict) -> dict:
        return self.provider.create_issue(fields)

    def update(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def update_raw(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def transition(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)

    def transition_raw(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)
