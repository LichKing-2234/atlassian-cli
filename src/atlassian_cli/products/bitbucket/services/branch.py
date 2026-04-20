from atlassian_cli.products.bitbucket.schemas import BitbucketBranch


class BranchService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, filter_text: str | None) -> "list[dict]":
        return [
            self._normalize_branch(item)
            for item in self.provider.list_branches(project_key, repo_slug, filter_text)
        ]

    def list_raw(self, project_key: str, repo_slug: str, filter_text: str | None) -> "list[dict]":
        return self.provider.list_branches(project_key, repo_slug, filter_text)

    def _normalize_branch(self, raw: dict) -> dict:
        branch = BitbucketBranch(
            id=raw.get("id"),
            display_id=raw.get("displayId"),
            latest_commit=raw.get("latestCommit"),
        )
        return branch.model_dump(exclude_none=True)
