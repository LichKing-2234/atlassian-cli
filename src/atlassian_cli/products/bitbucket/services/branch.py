from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketRef


class BranchService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, filter_text: str | None) -> dict:
        branches = [
            BitbucketRef.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_branches(project_key, repo_slug, filter_text)
        ]
        return {"results": branches}

    def list_raw(
        self, project_key: str, repo_slug: str, filter_text: str | None
    ) -> "list[dict]":
        return self.provider.list_branches(project_key, repo_slug, filter_text)
