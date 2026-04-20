from atlassian_cli.products.jira.schemas import JiraUser


class UserService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, username: str) -> dict:
        return self._normalize_user(self.provider.get_user(username))

    def get_raw(self, username: str) -> dict:
        return self.provider.get_user(username)

    def search(self, query: str) -> "list[dict]":
        return [self._normalize_user(item) for item in self.provider.search_users(query)]

    def search_raw(self, query: str) -> "list[dict]":
        return self.provider.search_users(query)

    def _normalize_user(self, raw: dict) -> dict:
        user = JiraUser(
            username=raw.get("name") or raw.get("key") or raw.get("username") or "",
            display_name=raw.get("displayName") or raw.get("display_name") or "",
            email=raw.get("emailAddress") or raw.get("email"),
        )
        return user.model_dump(exclude_none=True)
