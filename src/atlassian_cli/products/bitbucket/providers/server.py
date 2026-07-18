from itertools import islice

from atlassian import Bitbucket

from atlassian_cli.auth.headers import merge_headers
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
        self._headers = dict(headers or {})
        session = getattr(self.client, "_session", None)
        if session is not None:
            patch_session_headers(session, self._headers)

    def request_api(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None,
        params: dict[str, object] | None,
        json_body: dict[str, object] | None,
        data: bytes | None,
    ):
        url = self.client.url_joiner(self.client.url, path)
        request_headers = merge_headers(self._headers, headers or {})
        if not any(name.lower() == "accept" for name in request_headers):
            request_headers["Accept"] = "*/*"
        if json_body is not None and not any(
            name.lower() == "content-type" for name in request_headers
        ):
            request_headers["Content-Type"] = "application/json; charset=utf-8"
        retry_handler = self.client._retry_handler()
        while True:
            response = self.client._session.request(
                method=method,
                url=url,
                headers=request_headers,
                params=params,
                json=json_body,
                data=data,
                timeout=self.client.timeout,
                verify=self.client.verify_ssl,
                proxies=self.client.proxies,
                cert=self.client.cert,
                allow_redirects=False,
            )
            if not retry_handler(response):
                break
        response.encoding = "utf-8"
        return response

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

    def get_pull_request_diff_with_lines(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict:
        url = f"{self.client._url_pull_request(project_key, repo_slug, pr_id)}/diff"
        response = self.client.get(
            url,
            headers={"Accept": "application/json"},
            advanced_mode=True,
        )
        if hasattr(response, "json"):
            return response.json()
        return response

    def list_pull_request_activities(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_pull_requests_activities(
                project_key,
                repo_slug,
                pr_id,
                start=start,
                limit=limit,
            ),
            limit=limit,
        )

    def list_pull_request_changes(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_pull_requests_changes(
                project_key,
                repo_slug,
                pr_id,
                start=start,
                limit=limit,
            ),
            limit=limit,
        )

    def get_pull_request_mergeability(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.client.is_pull_request_can_be_merged(project_key, repo_slug, pr_id)

    def list_dashboard_pull_requests(
        self, *, role: str, state: str, start: int, limit: int
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_dashboard_pull_requests(
                start=start,
                limit=limit,
                role=role,
                state=None if state == "ALL" else state,
                order="NEWEST",
            ),
            limit=limit,
        )

    def approve_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        url = f"{self.client._url_pull_request(project_key, repo_slug, pr_id)}/approve"
        return self.client.post(url)

    def unapprove_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        url = f"{self.client._url_pull_request(project_key, repo_slug, pr_id)}/approve"
        return self.client.delete(url)

    def list_pull_request_comments(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        activities = self._paged_items(
            self.client.get_pull_requests_activities(
                project_key,
                repo_slug,
                pr_id,
                start=start,
                limit=limit,
            ),
            limit=limit,
        )
        return [
            comment
            for activity in activities
            if isinstance(activity, dict)
            for comment in [activity.get("comment")]
            if isinstance(comment, dict)
        ]

    def get_pull_request_comment(
        self, project_key: str, repo_slug: str, pr_id: int, comment_id: str
    ) -> dict:
        return self.client.get_pull_request_comment(project_key, repo_slug, pr_id, comment_id)

    def add_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        text: str,
        *,
        parent_id: str | None = None,
        anchor: dict | None = None,
    ) -> dict:
        if anchor is not None:
            body = {
                "text": text,
                "anchor": {
                    "path": anchor["path"],
                    "line": anchor["line"],
                    "lineType": anchor["line_type"],
                },
            }
            if parent_id:
                body["parent"] = {"id": parent_id}
            url = self.client._url_pull_request_comments(project_key, repo_slug, pr_id)
            return self.client.post(url, data=body)

        return self.client.add_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            text,
            parent_id=parent_id,
        )

    def update_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        text: str,
        *,
        version: int,
    ) -> dict:
        return self.client.update_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            text,
            version,
        )

    def delete_pull_request_comment(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        comment_id: str,
        *,
        version: int,
    ) -> dict | None:
        return self.client.delete_pull_request_comment(
            project_key,
            repo_slug,
            pr_id,
            comment_id,
            version,
        )

    def list_pull_request_commits(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int | None,
    ) -> list[dict]:
        return self._paged_items(
            self.client.get_pull_requests_commits(
                project_key,
                repo_slug,
                pr_id,
                start=start,
                limit=limit,
            ),
            limit=limit,
        )

    def get_associated_build_statuses(self, commit: str) -> dict:
        url = self.client.resource_url(
            f"commits/{commit}",
            api_root="rest/build-status",
        )
        return self.client.get(url, params={"limit": 100})

    def list_associated_build_statuses(self, commit: str) -> list[dict]:
        url = self.client.resource_url(
            f"commits/{commit}",
            api_root="rest/build-status",
        )
        params = {"limit": 100}
        page = self.client.get(url, params=params)
        if not isinstance(page, dict):
            raise ValueError("invalid paginated Bitbucket build status response")

        values = []
        current_start = 0
        seen_starts = {current_start}
        while True:
            page_values = page.get("values")
            if not isinstance(page_values, list) or not all(
                isinstance(item, dict) for item in page_values
            ):
                raise ValueError("invalid paginated Bitbucket build status values")
            values.extend(page_values)

            if "isLastPage" not in page:
                return values
            is_last_page = page["isLastPage"]
            if not isinstance(is_last_page, bool):
                raise ValueError("invalid Bitbucket pagination isLastPage")
            if is_last_page:
                return values

            next_start = page.get("nextPageStart")
            if (
                isinstance(next_start, bool)
                or not isinstance(next_start, int)
                or next_start <= current_start
                or next_start in seen_starts
            ):
                raise ValueError(f"invalid Bitbucket pagination nextPageStart: {next_start!r}")
            seen_starts.add(next_start)
            current_start = next_start
            page = self.client.get(url, params={**params, "start": next_start})
            if not isinstance(page, dict):
                raise ValueError("invalid paginated Bitbucket build status response")

    def create_pull_request(self, project_key: str, repo_slug: str, payload: dict) -> dict:
        return self.client.create_pull_request(project_key, repo_slug, data=payload)

    def update_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        payload: dict,
    ) -> dict:
        return self.client.update_pull_request(project_key, repo_slug, pr_id, payload)

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
