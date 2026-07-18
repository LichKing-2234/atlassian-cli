from typing import Any, Protocol


class BitbucketProvider(Protocol):
    def request_api(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None,
        params: dict[str, object] | None,
        json_body: dict[str, object] | None,
        data: bytes | None,
    ) -> Any: ...
    def list_projects(self, *, start: int, limit: int) -> list[dict]: ...
    def get_project(self, project_key: str) -> dict: ...
    def list_repos(self, *, project_key: str | None, start: int, limit: int) -> list[dict]: ...
    def get_repo(self, project_key: str, repo_slug: str) -> dict: ...
    def create_repo(self, *, project_key: str, name: str, scm_id: str) -> dict: ...
    def list_branches(
        self, project_key: str, repo_slug: str, filter_text: str | None
    ) -> list[dict]: ...
    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int,
        limit: int,
    ) -> list[dict]: ...
    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict: ...
    def get_pull_request_diff(self, project_key: str, repo_slug: str, pr_id: int) -> str: ...
    def get_pull_request_diff_with_lines(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict: ...
    def list_pull_request_activities(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]: ...
    def list_pull_request_changes(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]: ...
    def get_pull_request_mergeability(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict: ...
    def list_dashboard_pull_requests(
        self, *, role: str, state: str, start: int, limit: int
    ) -> list[dict]: ...
    def approve_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict: ...
    def unapprove_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict: ...
    def list_pull_request_comments(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]: ...
    def get_pull_request_comment(
        self, project_key: str, repo_slug: str, pr_id: int, comment_id: str
    ) -> dict: ...
    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        parent_id: str | None = None,
        anchor: dict | None = None,
    ) -> dict: ...
    def update_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        text: str,
        *,
        version: int,
    ) -> dict: ...
    def delete_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        *,
        version: int,
    ) -> dict | None: ...
    def list_pull_request_commits(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int | None,
    ) -> list[dict]: ...
    def get_associated_build_statuses(self, commit: str) -> dict: ...
    def list_associated_build_statuses(self, commit: str) -> list[dict]: ...
    def create_pull_request(self, project_key: str, repo_slug: str, payload: dict) -> dict: ...
    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        merge_message: str,
        pr_version: int | None,
    ) -> dict: ...
