class PullRequestService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return self.provider.list_pull_requests(project_key, repo_slug, state)

    def get(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.get_pull_request(project_key, repo_slug, pr_id)

    def create(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.provider.create_pull_request(project_key, repo_slug, payload)

    def merge(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.provider.merge_pull_request(project_key, repo_slug, pr_id)
