from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraUser


class UserService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(self, username: str) -> dict:
        return JiraUser.from_api_response(self.provider.get_user(username)).to_simplified_dict()

    def get_raw(self, username: str) -> dict:
        return self.provider.get_user(username)

    def search(
        self,
        query: str,
        *,
        project_key: str | None,
        issue_key: str | None,
        limit: int,
    ) -> dict:
        users = [
            JiraUser.from_api_response(item).to_simplified_dict()
            for item in self.provider.search_users(
                query, project_key=project_key, issue_key=issue_key, limit=limit
            )
        ]
        return {"results": users}

    def search_raw(
        self,
        query: str,
        *,
        project_key: str | None,
        issue_key: str | None,
        limit: int,
    ) -> "list[dict]":
        return self.provider.search_users(
            query, project_key=project_key, issue_key=issue_key, limit=limit
        )
