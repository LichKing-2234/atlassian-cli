from atlassian_cli.products.jira.schemas import JiraProject


class ProjectService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self) -> "list[dict]":
        return [self._normalize_project(item) for item in self.provider.list_projects()]

    def get(self, project_key: str) -> dict:
        return self._normalize_project(self.provider.get_project(project_key))

    def list_raw(self) -> "list[dict]":
        return self.provider.list_projects()

    def get_raw(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)

    def _normalize_project(self, raw: dict) -> dict:
        project = JiraProject(
            key=raw["key"],
            name=raw["name"],
            project_type=raw.get("projectTypeKey"),
        )
        return project.model_dump(exclude_none=True)
