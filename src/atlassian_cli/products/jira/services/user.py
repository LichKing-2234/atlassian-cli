from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraUser


class UserService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def get(self, username: str) -> dict:
        return JiraUser.from_api_response(self.provider.get_user(username)).to_simplified_dict()

    def get_raw(self, username: str) -> dict:
        return self.provider.get_user(username)

    def search(self, query: str) -> dict:
        users = [
            JiraUser.from_api_response(item).to_simplified_dict()
            for item in self.provider.search_users(query)
        ]
        return {"results": users}

    def search_raw(self, query: str) -> "list[dict]":
        return self.provider.search_users(query)
