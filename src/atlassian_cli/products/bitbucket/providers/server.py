from atlassian import Bitbucket

from atlassian_cli.auth.session_patch import patch_session_headers


class BitbucketServerProvider:
    def __init__(
        self,
        *,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {
            "url": url,
            "username": username,
            "password": password or token,
        }
        self.client = Bitbucket(**kwargs)
        session = getattr(self.client, "_session", None)
        if session is not None:
            patch_session_headers(session, headers or {})

    def _paged_items(self, value) -> list[dict]:
        if isinstance(value, dict):
            return value.get("values", [])
        if isinstance(value, list):
            return value
        return list(value)

    def list_projects(self, *, start: int, limit: int) -> list[dict]:
        return self._paged_items(self.client.project_list(limit=limit, start=start))

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def list_repos(self, *, project_key: str | None, start: int, limit: int) -> list[dict]:
        return self._paged_items(
            self.client.repo_list(project_key=project_key, limit=limit, start=start)
        )

    def get_repo(self, project_key: str, repo_slug: str) -> dict:
        return self.client.get_repo(project_key, repo_slug)

    def create_repo(self, *, project_key: str, name: str, scm_id: str) -> dict:
        return self.client.create_repo(project_key=project_key, name=name, scm_id=scm_id)

    def list_branches(
        self, project_key: str, repo_slug: str, filter_text: str | None
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_branches(project_key, repo_slug, filter=filter_text)
        )

    def list_pull_requests(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return self._paged_items(self.client.get_pull_requests(project_key, repo_slug, state=state))

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.client.get_pull_request(project_key, repo_slug, pr_id)

    def create_pull_request(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.client.create_pull_request(project_key, repo_slug, data=payload)

    def merge_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.client.merge_pull_request(project_key, repo_slug, pr_id)
