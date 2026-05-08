from typing import Any

from atlassian_cli.core.errors import TransportError
from atlassian_cli.models.common import first_present, nested_get
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider
from atlassian_cli.products.bitbucket.schemas import (
    BitbucketBuildStatus,
    BitbucketCommitBuildStatusSummary,
    BitbucketPullRequestBuildStatusSummary,
)

STATE_RANK = {"FAILED": 3, "INPROGRESS": 2, "SUCCESSFUL": 1, "UNKNOWN": 0}


def _extract_items(value: object, *, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        values = value.get("values", [])
        return [item for item in values if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise TransportError(
        f"{label} was not a JSON object or array. "
        "The server returned a non-JSON response; check authentication headers."
    )


def _state_for_items(items: list[dict[str, Any]]) -> str:
    state = "UNKNOWN"
    for item in items:
        candidate = str(item.get("state") or "UNKNOWN").upper()
        if STATE_RANK.get(candidate, 0) > STATE_RANK[state]:
            state = candidate if candidate in STATE_RANK else "UNKNOWN"
    return state


def _state_for_summaries(items: list[dict[str, Any]]) -> str:
    state = "UNKNOWN"
    for item in items:
        candidate = str(item.get("overall_state") or "UNKNOWN").upper()
        if STATE_RANK.get(candidate, 0) > STATE_RANK[state]:
            state = candidate if candidate in STATE_RANK else "UNKNOWN"
    return state


class BuildStatusService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def for_commit(self, commit: str) -> dict:
        raw = self.provider.get_associated_build_statuses(commit)
        return self._commit_summary(commit, raw)

    def for_commit_raw(self, commit: str) -> dict:
        return self.provider.get_associated_build_statuses(commit)

    def for_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        latest_only: bool = False,
    ) -> dict:
        commits = (
            self._latest_commit(project_key, repo_slug, pr_id)
            if latest_only
            else self._all_commits(project_key, repo_slug, pr_id)
        )
        commit_summaries = [self.for_commit(commit) for commit in commits]
        summary = BitbucketPullRequestBuildStatusSummary(
            pull_request={"id": pr_id, "project_key": project_key, "repo_slug": repo_slug},
            overall_state=_state_for_summaries(commit_summaries),
            commits=commit_summaries,
        )
        return summary.to_simplified_dict()

    def for_pull_request_raw(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        latest_only: bool = False,
    ) -> dict:
        return self.for_pull_request(
            project_key,
            repo_slug,
            pr_id,
            latest_only=latest_only,
        )

    def _commit_summary(self, commit: str, raw: object) -> dict:
        statuses = [
            BitbucketBuildStatus.from_api_response(item).to_simplified_dict()
            for item in _extract_items(raw, label="Bitbucket build status response")
        ]
        summary = BitbucketCommitBuildStatusSummary(
            commit=commit,
            overall_state=_state_for_items(statuses),
            results=statuses,
        )
        return summary.to_simplified_dict()

    def _all_commits(self, project_key: str, repo_slug: str, pr_id: int) -> list[str]:
        commits = self.provider.list_pull_request_commits(
            project_key,
            repo_slug,
            pr_id,
            start=0,
            limit=None,
        )
        return [commit for commit in [self._commit_id(item) for item in commits] if commit]

    def _latest_commit(self, project_key: str, repo_slug: str, pr_id: int) -> list[str]:
        pull_request = self.provider.get_pull_request(project_key, repo_slug, pr_id)
        latest = nested_get(pull_request, "fromRef", "latestCommit")
        if latest:
            return [str(latest)]
        commits = self._all_commits(project_key, repo_slug, pr_id)
        return commits[:1]

    @staticmethod
    def _commit_id(item: dict[str, Any]) -> str | None:
        value = first_present(item.get("id"), item.get("displayId"), item.get("hash"))
        return str(value) if value else None
