from atlassian_cli.products.bitbucket.schemas import BitbucketProject


class ProjectService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> "list[dict]":
        return [
            self._normalize_project(item)
            for item in self.provider.list_projects(start=start, limit=limit)
        ]

    def get(self, project_key: str) -> dict:
        return self._normalize_project(self.provider.get_project(project_key))

    def list_raw(self, start: int, limit: int) -> "list[dict]":
        return self.provider.list_projects(start=start, limit=limit)

    def get_raw(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)

    def _normalize_project(self, raw: dict) -> dict:
        project = BitbucketProject(
            key=raw["key"],
            name=raw["name"],
        )
        return project.model_dump(exclude_none=True)
