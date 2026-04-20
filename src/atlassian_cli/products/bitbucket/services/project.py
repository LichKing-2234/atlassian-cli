class ProjectService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> list[dict]:
        return self.provider.list_projects(start=start, limit=limit)

    def get(self, project_key: str) -> dict:
        return self.provider.get_project(project_key)
