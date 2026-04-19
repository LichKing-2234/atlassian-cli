class BranchService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, filter_text: str | None) -> list[dict]:
        return self.provider.list_branches(project_key, repo_slug, filter_text)
