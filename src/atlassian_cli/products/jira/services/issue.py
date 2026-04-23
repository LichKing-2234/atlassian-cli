from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraIssue, JiraSearchResult


class IssueService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(self, issue_key: str) -> dict:
        return JiraIssue.from_api_response(self.provider.get_issue(issue_key)).to_simplified_dict()

    def get_raw(self, issue_key: str) -> dict:
        return self.provider.get_issue(issue_key)

    def search(self, jql: str, start: int, limit: int) -> dict:
        raw = self.provider.search_issues(jql, start, limit)
        return JiraSearchResult.from_api_response(raw).to_simplified_dict()

    def search_raw(self, jql: str, start: int, limit: int) -> dict:
        return self.provider.search_issues(jql, start, limit)

    def create(self, fields: dict) -> dict:
        raw = self.provider.create_issue(fields)
        if isinstance(raw, dict) and "fields" in raw and "key" in raw:
            return JiraIssue.from_api_response(raw).to_simplified_dict()
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
