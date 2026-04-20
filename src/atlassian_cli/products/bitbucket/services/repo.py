from atlassian_cli.products.bitbucket.schemas import BitbucketRepo


class RepoService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str | None, start: int, limit: int) -> list[dict]:
        return self.provider.list_repos(project_key=project_key, start=start, limit=limit)

    def get(self, project_key: str, repo_slug: str) -> dict:
        raw = self.provider.get_repo(project_key, repo_slug)
        repo = BitbucketRepo(
            project=raw["project"],
            slug=raw["slug"],
            name=raw["name"],
            state=raw["state"],
        )
        return repo.model_dump(exclude_none=True)

    def get_raw(self, project_key: str, repo_slug: str) -> dict:
        return self.provider.get_repo(project_key, repo_slug)

    def create(self, project_key: str, name: str, scm_id: str) -> dict:
        return self.provider.create_repo(project_key=project_key, name=name, scm_id=scm_id)
