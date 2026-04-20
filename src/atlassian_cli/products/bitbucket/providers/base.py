from typing import Protocol


class BitbucketProvider(Protocol):
    def list_repos(self, project_key: str | None, limit: int, start: int) -> list[dict]: ...
