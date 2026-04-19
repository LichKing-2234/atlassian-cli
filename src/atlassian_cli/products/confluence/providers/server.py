from atlassian import Confluence


class ConfluenceServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Confluence(url=url, username=username, password=password or token)
