from atlassian import Jira


class JiraServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Jira(url=url, username=username, password=password or token)
