from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketRepo


class RepoService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, project_key: str | None, start: int, limit: int) -> dict:
        repos = [
            BitbucketRepo.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_repos(project_key=project_key, start=start, limit=limit)
        ]
        return {"results": repos, "start_at": start, "max_results": limit}

    def get(self, project_key: str, repo_slug: str) -> dict:
        return BitbucketRepo.from_api_response(
            self.provider.get_repo(project_key, repo_slug)
        ).to_simplified_dict()

    def list_raw(self, project_key: str | None, start: int, limit: int) -> "list[dict]":
        return self.provider.list_repos(project_key=project_key, start=start, limit=limit)

    def get_raw(self, project_key: str, repo_slug: str) -> dict:
        return self.provider.get_repo(project_key, repo_slug)

    def create(self, project_key: str, name: str, scm_id: str) -> dict:
        return BitbucketRepo.from_api_response(
            self.provider.create_repo(project_key=project_key, name=name, scm_id=scm_id)
        ).to_simplified_dict()

    def create_raw(self, project_key: str, name: str, scm_id: str) -> dict:
        return self.provider.create_repo(project_key=project_key, name=name, scm_id=scm_id)
