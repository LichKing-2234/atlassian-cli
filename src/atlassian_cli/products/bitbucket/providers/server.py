from itertools import islice

from atlassian import Bitbucket

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.auth.session_patch import patch_session_headers


class BitbucketServerProvider:
    def __init__(
        self,
        *,
        auth_mode: AuthMode = AuthMode.BASIC,
        url: str,
        username: str | None,
        password: str | None,
        token: str | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        kwargs = {"url": url}
        if auth_mode in {AuthMode.PAT, AuthMode.BEARER} and token is not None:
            kwargs["token"] = token
        else:
            kwargs["username"] = username
            kwargs["password"] = password or token
        self.client = Bitbucket(**kwargs)
        session = getattr(self.client, "_session", None)
        if session is not None:
            patch_session_headers(session, headers or {})

    def _paged_items(self, value, *, limit: int | None = None) -> list[dict]:
        if isinstance(value, dict):
            values = value.get("values", [])
            return values[:limit] if limit is not None else values
        if isinstance(value, list):
            return value[:limit] if limit is not None else value
        if limit is not None:
            return list(islice(value, limit))
        return list(value)

    def list_projects(self, *, start: int, limit: int) -> list[dict]:
        return self._paged_items(self.client.project_list(limit=limit, start=start), limit=limit)

    def get_project(self, project_key: str) -> dict:
        return self.client.project(project_key)

    def list_repos(self, *, project_key: str | None, start: int, limit: int) -> list[dict]:
        return self._paged_items(
            self.client.repo_list(project_key=project_key, limit=limit, start=start),
            limit=limit,
        )

    def get_repo(self, project_key: str, repo_slug: str) -> dict:
        return self.client.get_repo(project_key, repo_slug)

    def create_repo(self, *, project_key: str, name: str, scm_id: str) -> dict:
        if scm_id != "git":
            raise ValueError(
                f"Unsupported scm_id for Bitbucket Server: {scm_id!r}. Only 'git' is supported."
            )
        return self.client.create_repo(project_key, name)

    def list_branches(
        self, project_key: str, repo_slug: str, filter_text: str | None
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_branches(project_key, repo_slug, filter=filter_text)
        )

    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_pull_requests(
                project_key,
                repo_slug,
                state=state,
                limit=limit,
                start=start,
            ),
            limit=limit,
        )

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.client.get_pull_request(project_key, repo_slug, pr_id)

    def get_pull_request_diff(self, project_key: str, repo_slug: str, pr_id: int) -> str:
        url = f"{self.client._url_pull_request(project_key, repo_slug, pr_id)}.diff"
        response = self.client.get(url, headers={"Accept": "text/plain"}, advanced_mode=True)
        return response.text

    def create_pull_request(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.client.create_pull_request(project_key, repo_slug, data=payload)

    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        merge_message: str,
        pr_version: int | None,
    ) -> dict:
        return self.client.merge_pull_request(
            project_key,
            repo_slug,
            pr_id,
            merge_message,
            pr_version=pr_version,
        )
