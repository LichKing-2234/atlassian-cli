from atlassian import Bitbucket


class BitbucketServerProvider:
    def __init__(self, *, url: str, username: str | None, password: str | None, token: str | None) -> None:
        self.client = Bitbucket(url=url, username=username, password=password or token)
