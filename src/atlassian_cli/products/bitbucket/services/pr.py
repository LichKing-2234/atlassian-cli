from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequest


class PullRequestService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, state: str) -> dict:
        prs = [
            BitbucketPullRequest.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_pull_requests(project_key, repo_slug, state)
        ]
        return {"results": prs}

    def list_raw(self, project_key: str, repo_slug: str, state: str) -> "list[dict]":
        return self.provider.list_pull_requests(project_key, repo_slug, state)

    def get(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return BitbucketPullRequest.from_api_response(
            self.provider.get_pull_request(project_key, repo_slug, pr_id)
        ).to_simplified_dict()

    def get_raw(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.get_pull_request(project_key, repo_slug, pr_id)

    def create(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return BitbucketPullRequest.from_api_response(
            self.provider.create_pull_request(project_key, repo_slug, payload)
        ).to_simplified_dict()

    def create_raw(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.provider.create_pull_request(project_key, repo_slug, payload)

    def merge(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        current = self.provider.get_pull_request(project_key, repo_slug, pr_id)
        title = current.get("title") or f"Pull request {pr_id}"
        version = current.get("version")
        raw = self.provider.merge_pull_request(
            project_key,
            repo_slug,
            pr_id,
            merge_message=f"Merge pull request #{pr_id}: {title}",
            pr_version=version,
        )
        return BitbucketPullRequest.from_api_response(raw).to_simplified_dict()

    def merge_raw(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        current = self.provider.get_pull_request(project_key, repo_slug, pr_id)
        title = current.get("title") or f"Pull request {pr_id}"
        version = current.get("version")
        return self.provider.merge_pull_request(
            project_key,
            repo_slug,
            pr_id,
            merge_message=f"Merge pull request #{pr_id}: {title}",
            pr_version=version,
        )
