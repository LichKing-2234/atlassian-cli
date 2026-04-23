from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraProject


class ProjectService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def list(self) -> dict:
        projects = [
            JiraProject.from_api_response(item).to_simplified_dict()
            for item in self.provider.list_projects()
        ]
        return {"results": projects}

    def get(self, project_key: str) -> dict:
        return JiraProject.from_api_response(
            self.provider.get_project(project_key)
        ).to_simplified_dict()

    def list_raw(self) -> "list[dict]":
        return self.provider.list_projects()

    def get_raw(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
