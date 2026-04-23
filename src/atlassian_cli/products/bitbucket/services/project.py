from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import BitbucketProject


class ProjectService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> dict:
        projects = [
            BitbucketProject.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_projects(start=start, limit=limit)
        ]
        return {"results": projects, "start_at": start, "max_results": limit}

    def get(self, project_key: str) -> dict:
        return BitbucketProject.from_api_response(
            self.provider.get_project(project_key)
        ).to_simplified_dict()

    def list_raw(self, start: int, limit: int) -> "list[dict]":
        return self.provider.list_projects(start=start, limit=limit)

    def get_raw(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
