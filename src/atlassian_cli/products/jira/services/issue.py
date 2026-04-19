from atlassian_cli.products.jira.schemas import JiraIssue


class IssueService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, issue_key: str) -> dict:
        raw = self.provider.get_issue(issue_key)
        issue = JiraIssue(
            key=raw["key"],
            summary=raw["fields"]["summary"],
            status=raw["fields"]["status"]["name"],
            assignee=(raw["fields"].get("assignee") or {}).get("displayName"),
            reporter=(raw["fields"].get("reporter") or {}).get("displayName"),
            priority=(raw["fields"].get("priority") or {}).get("name"),
            updated=raw["fields"].get("updated"),
        )
        return issue.model_dump()

    def search(self, jql: str, start: int, limit: int) -> list[dict]:
        return [self.get(item["key"]) for item in self.provider.search_issues(jql, start, limit)]

    def create(self, fields: dict) -> dict:
        return self.provider.create_issue(fields)

    def update(self, issue_key: str, fields: dict) -> dict:
        return self.provider.update_issue(issue_key, fields)

    def transition(self, issue_key: str, transition: str) -> dict:
        return self.provider.transition_issue(issue_key, transition)
