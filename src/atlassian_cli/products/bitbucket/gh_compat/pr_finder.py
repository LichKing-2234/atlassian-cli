from atlassian_cli.core.errors import NotFoundError, ValidationError
from atlassian_cli.products.bitbucket.gh_compat.repository_context import RepositoryResolution
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryRef,
    ServerIdentity,
    parse_pull_request_url,
)
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider


def _rank(raw: dict) -> tuple[int, int, int]:
    return (
        1 if raw.get("state") == "OPEN" else 0,
        int(raw.get("createdDate") or 0),
        int(raw.get("id") or 0),
    )


class PullRequestFinder:
    def __init__(self, provider: BitbucketProvider, server: ServerIdentity) -> None:
        self.provider = provider
        self.server = server

    def find(
        self,
        selector: str | None,
        resolution: RepositoryResolution,
        *,
        explicit_repo: bool,
    ) -> PullRequestRef:
        if selector and "://" in selector:
            return parse_pull_request_url(selector, self.server)
        if selector is None and explicit_repo:
            raise ValidationError("argument required when using the --repo flag")
        if selector is None:
            selector = resolution.current_branch
            if selector is None:
                raise NotFoundError("no pull request found for the current branch")
        if selector.isdecimal():
            number = int(selector)
            if number < 1:
                raise ValidationError("pull request number must be greater than zero")
            return PullRequestRef(resolution.repository, number)
        project, branch = self._split_branch(selector, resolution.repository.project_key)
        matches = [
            raw
            for raw in self._all_candidates(resolution.repository)
            if self._matches(raw, project, resolution.repository.repo_slug, branch)
        ]
        if not matches:
            raise NotFoundError(f"no pull request found for branch {selector}")
        selected = max(matches, key=_rank)
        return PullRequestRef(resolution.repository, int(selected["id"]))

    @staticmethod
    def _split_branch(selector: str, default_project: str) -> tuple[str, str]:
        project, separator, branch = selector.partition(":")
        if separator and project and branch:
            return project, branch
        return default_project, selector

    def _all_candidates(self, repository: RepositoryRef) -> list[dict]:
        candidates: list[dict] = []
        seen_ids: set[object] = set()
        for state in ("OPEN", "DECLINED", "MERGED"):
            start = 0
            while True:
                page = self.provider.list_pull_requests(
                    repository.project_key,
                    repository.repo_slug,
                    state,
                    start=start,
                    limit=100,
                )
                for raw in page:
                    pull_request_id = raw.get("id")
                    if pull_request_id in seen_ids:
                        continue
                    seen_ids.add(pull_request_id)
                    candidates.append(raw)
                if len(page) < 100:
                    break
                start += 100
        return candidates

    @staticmethod
    def _matches(raw: dict, project: str, repo: str, branch: str) -> bool:
        source_ref = raw.get("fromRef") or {}
        source_repo = source_ref.get("repository") or {}
        source_project = source_repo.get("project") or {}
        return (
            source_project.get("key") == project
            and source_repo.get("slug") == repo
            and source_ref.get("displayId") == branch
        )
