from __future__ import annotations

import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from atlassian_cli.products.bitbucket.diff import normalize_pull_request_diff
from atlassian_cli.products.bitbucket.gh_compat.selectors import PullRequestRef, RepositoryRef
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider

DIFF_FIELDS = {"additions", "changedFiles", "deletions", "files"}
ACTIVITY_FIELDS = {"comments", "mergedAt", "mergedBy"}
COMMIT_FIELDS = {"commits"}
MERGEABILITY_FIELDS = {"mergeable", "mergeStateStatus"}
BUILD_FIELDS = {"statusCheckRollup"}
PRESENTER_REVIEWERS_FIELD = "_reviewers"

BITBUCKET_PULL_REQUEST_STATES = frozenset({"OPEN", "DECLINED", "MERGED", "ALL"})
_CHANGE_TYPE_MAP = {
    "ADD": "ADDED",
    "DELETE": "DELETED",
    "MOVE": "RENAMED",
    "COPY": "COPIED",
}
_N03_QUALIFIERS = {"app", "assignee", "draft", "label", "milestone", "project", "team"}
_REVIEW_VALUES = {"none", "required", "approved", "changes_requested"}
_STATUS_VALUES = {"pending", "success", "failure"}


@dataclass(frozen=True)
class PullRequestListFilters:
    state: str = "OPEN"
    limit: int = 30
    author: str | None = None
    base: str | None = None
    head: str | None = None
    search: str | None = None


@dataclass(frozen=True)
class PullRequestListResult:
    items: list[dict]
    total_count: int | None


def normalize_pull_request_state(value: str) -> str:
    normalized = value.upper()
    if normalized not in BITBUCKET_PULL_REQUEST_STATES:
        raise ValueError(f"invalid state: {value}")
    return normalized


def _rfc3339(value: object) -> str | None:
    if value is None:
        return None
    instant = datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    return instant.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _user(raw_user: object) -> dict | None:
    if not isinstance(raw_user, Mapping):
        return None
    slug = raw_user.get("slug")
    login = raw_user.get("name") or slug or ""
    display_name = raw_user.get("displayName") or raw_user.get("name") or slug or ""
    user_id = raw_user.get("id") or slug or login
    return {
        "id": str(user_id),
        "is_bot": False,
        "login": login,
        "name": display_name,
    }


def _project_object(raw_repository: object) -> dict | None:
    if not isinstance(raw_repository, Mapping):
        return None
    project = raw_repository.get("project")
    if not isinstance(project, Mapping):
        return None
    login = project.get("key") or project.get("name") or ""
    name = project.get("name") or project.get("key") or ""
    return {"id": str(project.get("id") or login), "login": login, "name": name}


def _repository_object(raw_repository: object) -> dict | None:
    if not isinstance(raw_repository, Mapping):
        return None
    project = raw_repository.get("project")
    project_key = project.get("key") if isinstance(project, Mapping) else ""
    name = raw_repository.get("name") or raw_repository.get("slug") or ""
    slug = raw_repository.get("slug") or name
    return {
        "id": str(raw_repository.get("id") or slug),
        "name": name,
        "nameWithOwner": f"{project_key}/{slug}" if project_key else str(slug),
    }


def _repository_identity(raw_ref: object) -> tuple[object, object]:
    if not isinstance(raw_ref, Mapping):
        return (None, None)
    repository = raw_ref.get("repository")
    if not isinstance(repository, Mapping):
        return (None, None)
    project = repository.get("project")
    project_key = project.get("key") if isinstance(project, Mapping) else None
    return (project_key, repository.get("slug"))


def _review_decision(reviewers: object) -> str | None:
    if not isinstance(reviewers, list) or not reviewers:
        return None
    statuses = {str(item.get("status") or "").upper() for item in reviewers}
    if "NEEDS_WORK" in statuses:
        return "CHANGES_REQUESTED"
    if all(bool(item.get("approved")) or item.get("status") == "APPROVED" for item in reviewers):
        return "APPROVED"
    return "REVIEW_REQUIRED"


def _review_requests(reviewers: object) -> list[dict]:
    if not isinstance(reviewers, list):
        return []
    return [
        mapped
        for reviewer in reviewers
        if not bool(reviewer.get("approved")) and reviewer.get("status") != "APPROVED"
        for mapped in [_user(reviewer.get("user"))]
        if mapped is not None
    ]


def _presenter_reviewers(reviewers: object) -> list[dict]:
    if not isinstance(reviewers, list):
        return []
    projected = []
    for reviewer in reviewers:
        if not isinstance(reviewer, Mapping):
            continue
        user = _user(reviewer.get("user"))
        if user is None:
            continue
        status = reviewer.get("status")
        if not status:
            status = "APPROVED" if reviewer.get("approved") else "UNAPPROVED"
        projected.append({"user": user, "status": str(status)})
    return projected


def _first_self_link(raw: Mapping[str, Any]) -> str:
    links = raw.get("links")
    self_links = links.get("self") if isinstance(links, Mapping) else None
    if not isinstance(self_links, list) or not self_links:
        return ""
    first = self_links[0]
    return str(first.get("href") or "") if isinstance(first, Mapping) else ""


def _closed_at(raw: Mapping[str, Any]) -> str | None:
    if raw.get("state") == "OPEN":
        return None
    return _rfc3339(raw.get("closedDate") or raw.get("updatedDate"))


def _direct_projection(raw: Mapping[str, Any]) -> dict[str, Any]:
    from_ref = raw["fromRef"]
    to_ref = raw["toRef"]
    return {
        "author": _user((raw.get("author") or {}).get("user")),
        "baseRefName": to_ref.get("displayId"),
        "baseRefOid": to_ref.get("latestCommit"),
        "body": raw.get("description") or "",
        "closed": raw.get("state") != "OPEN",
        "closedAt": _closed_at(raw),
        "createdAt": _rfc3339(raw.get("createdDate")),
        "fullDatabaseId": str(raw["id"]),
        "headRefName": from_ref.get("displayId"),
        "headRefOid": from_ref.get("latestCommit"),
        "headRepository": _repository_object(from_ref.get("repository")),
        "headRepositoryOwner": _project_object(from_ref.get("repository")),
        "id": str(raw["id"]),
        "isCrossRepository": _repository_identity(from_ref) != _repository_identity(to_ref),
        "number": int(raw["id"]),
        "reviewDecision": _review_decision(raw.get("reviewers", [])),
        "reviewRequests": _review_requests(raw.get("reviewers", [])),
        PRESENTER_REVIEWERS_FIELD: _presenter_reviewers(raw.get("reviewers", [])),
        "state": raw["state"],
        "title": raw.get("title") or "",
        "updatedAt": _rfc3339(raw.get("updatedDate")),
        "url": _first_self_link(raw),
    }


def _path_to_string(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        return ""
    for key in ("toString", "path", "displayId", "name"):
        item = value.get(key)
        if item:
            return str(item)
    return ""


def _extract_values(value: object) -> list[dict]:
    if isinstance(value, Mapping):
        value = value.get("values", [])
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return [item for item in value if isinstance(item, dict)]


def _comment(raw_comment: Mapping[str, Any]) -> dict:
    return {
        "id": str(raw_comment["id"]),
        "url": _first_self_link(raw_comment),
        "body": raw_comment.get("text") or "",
        "author": _user(raw_comment.get("author")),
        "authorAssociation": "NONE",
        "createdAt": _rfc3339(raw_comment.get("createdDate")),
        "updatedAt": _rfc3339(raw_comment.get("updatedDate")),
    }


def _commit(raw_commit: Mapping[str, Any]) -> dict:
    message_lines = (raw_commit.get("message") or "").splitlines()
    return {
        "oid": raw_commit.get("id"),
        "messageHeadline": message_lines[0] if message_lines else "",
        "messageBody": "\n".join(message_lines[1:]),
        "authoredDate": _rfc3339(raw_commit.get("authorTimestamp")),
        "committedDate": _rfc3339(raw_commit.get("committerTimestamp")),
        "authors": [_user(raw_commit.get("author"))],
    }


def _normalize_build_state(value: object) -> str:
    return {
        "SUCCESSFUL": "SUCCESS",
        "FAILED": "FAILURE",
        "INPROGRESS": "PENDING",
    }.get(str(value or "").upper(), "PENDING")


def _status_context(raw_build: Mapping[str, Any]) -> dict:
    return {
        "__typename": "StatusContext",
        "context": raw_build.get("key") or "",
        "state": _normalize_build_state(raw_build.get("state")),
        "targetUrl": raw_build.get("url") or "",
        "startedAt": _rfc3339(raw_build.get("dateAdded")),
    }


def parse_search_query(value: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {
        "terms": [],
        "scopes": set(),
        "qualifiers": [],
        "has_state": False,
    }
    for token in shlex.split(value or ""):
        negated = token.startswith("-") and len(token) > 1
        candidate = token[1:] if negated else token
        key, separator, qualifier_value = candidate.partition(":")
        key = key.lower()
        if separator and key in _N03_QUALIFIERS:
            raise ValueError(f"unsupported search qualifier: {key}")
        if separator and key == "in":
            scope = qualifier_value.lower()
            if negated or scope not in {"title", "body"}:
                raise ValueError(f"unsupported search qualifier: {candidate}")
            query["scopes"].add(scope)
            continue
        if separator and key in {"state", "is"}:
            try:
                normalized = normalize_pull_request_state(qualifier_value)
            except ValueError:
                raise ValueError(f"unsupported {key} search value: {qualifier_value}")
            query["qualifiers"].append(("state", normalized, negated))
            query["has_state"] = True
            continue
        if separator and key == "review":
            normalized = qualifier_value.lower()
            if normalized not in _REVIEW_VALUES:
                raise ValueError(f"unsupported review search value: {qualifier_value}")
            query["qualifiers"].append((key, normalized, negated))
            continue
        if separator and key == "status":
            normalized = qualifier_value.lower()
            if normalized not in _STATUS_VALUES:
                raise ValueError(f"unsupported status search value: {qualifier_value}")
            query["qualifiers"].append((key, normalized, negated))
            continue
        if separator and key in {"author", "base", "head"}:
            if not qualifier_value:
                raise ValueError(f"search qualifier {key} requires a value")
            query["qualifiers"].append((key, qualifier_value, negated))
            continue
        if candidate:
            query["terms"].append((candidate.casefold(), negated))
    if not query["scopes"]:
        query["scopes"] = {"title", "body"}
    return query


def _same_text(left: object, right: object) -> bool:
    return str(left or "").casefold() == str(right or "").casefold()


def _author_login(raw: Mapping[str, Any]) -> str:
    author = raw.get("author")
    user = author.get("user") if isinstance(author, Mapping) else None
    if not isinstance(user, Mapping):
        return ""
    return str(user.get("name") or user.get("slug") or "")


def _head_matches(raw: Mapping[str, Any], value: str) -> bool:
    from_ref = raw.get("fromRef")
    if not isinstance(from_ref, Mapping):
        return False
    branch = str(from_ref.get("displayId") or "")
    repository = from_ref.get("repository")
    project = repository.get("project") if isinstance(repository, Mapping) else None
    project_key = project.get("key") if isinstance(project, Mapping) else None
    return _same_text(branch, value) or (
        project_key is not None and _same_text(f"{project_key}:{branch}", value)
    )


def _review_matches(raw: Mapping[str, Any], value: str) -> bool:
    reviewers = raw.get("reviewers")
    if value == "none":
        return not reviewers
    return {
        "required": "REVIEW_REQUIRED",
        "approved": "APPROVED",
        "changes_requested": "CHANGES_REQUESTED",
    }[value] == _review_decision(reviewers)


def _rollup_state(statuses: list[dict]) -> str | None:
    states = {item.get("state") for item in statuses}
    if "FAILURE" in states:
        return "failure"
    if "PENDING" in states:
        return "pending"
    if states and states <= {"SUCCESS"}:
        return "success"
    return None


class PullRequestReadService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def list(
        self,
        repository: RepositoryRef,
        filters: PullRequestListFilters,
        fields: set[str],
        *,
        count_total: bool = False,
    ) -> PullRequestListResult:
        if filters.limit < 1:
            raise ValueError("limit must be greater than zero")
        query = parse_search_query(filters.search)
        for key, value in (
            ("author", filters.author),
            ("base", filters.base),
            ("head", filters.head),
        ):
            if value is not None:
                query["qualifiers"].append((key, value, False))

        state = normalize_pull_request_state(filters.state)
        if state == "OPEN" and query["has_state"]:
            state = "ALL"
        author_me_qualifiers = [
            (value, negated)
            for key, value, negated in query["qualifiers"]
            if key == "author" and _same_text(value, "@me")
        ]
        use_dashboard = any(not negated for _, negated in author_me_qualifiers)
        me_ids: set[object] = set()
        if author_me_qualifiers and not use_dashboard:
            me_ids = {raw.get("id") for raw in self._dashboard_pull_requests(repository, state)}

        items: list[dict] = []
        matched = 0
        seen_ids: set[object] = set()
        start = 0
        while True:
            if use_dashboard:
                raw_page = self.provider.list_dashboard_pull_requests(
                    role="AUTHOR",
                    state=state,
                    start=start,
                    limit=100,
                )
                page = [raw for raw in raw_page if self._belongs_to(repository, raw)]
                me_ids.update(raw.get("id") for raw in page)
            else:
                page = self.provider.list_pull_requests(
                    repository.project_key,
                    repository.repo_slug,
                    state,
                    start=start,
                    limit=100,
                )
                raw_page = page
            for raw in page:
                pull_request_id = raw.get("id")
                if pull_request_id in seen_ids:
                    continue
                seen_ids.add(pull_request_id)
                matches, precomputed = self._matches(raw, query, me_ids)
                if not matches:
                    continue
                matched += 1
                if len(items) < filters.limit:
                    items.append(self._project(repository, raw, fields, precomputed=precomputed))
                if not count_total and len(items) == filters.limit:
                    return PullRequestListResult(items, None)
            if len(raw_page) < 100:
                break
            start += 100
        return PullRequestListResult(items, matched if count_total else None)

    def get(self, ref: PullRequestRef, fields: set[str]) -> dict:
        raw = self.provider.get_pull_request(
            ref.repository.project_key,
            ref.repository.repo_slug,
            ref.number,
        )
        return self._project(ref.repository, raw, fields)

    def _project(
        self,
        repository: RepositoryRef,
        raw: Mapping[str, Any],
        fields: set[str],
        *,
        precomputed: Mapping[str, Any] | None = None,
    ) -> dict:
        available = _direct_projection(raw)
        available.update(precomputed or {})
        if fields & DIFF_FIELDS:
            available.update(self._diff_fields(repository, raw))
        if fields & ACTIVITY_FIELDS:
            available.update(self._activity_fields(repository, raw))
        if fields & COMMIT_FIELDS:
            available["commits"] = [
                _commit(item)
                for item in self._page_pr_family(
                    repository,
                    raw,
                    self.provider.list_pull_request_commits,
                )
            ]
        if fields & MERGEABILITY_FIELDS:
            available.update(self._mergeability_fields(repository, raw))
        if fields & BUILD_FIELDS and "statusCheckRollup" not in available:
            head_sha = (raw.get("fromRef") or {}).get("latestCommit")
            builds = self.provider.list_associated_build_statuses(str(head_sha)) if head_sha else []
            available["statusCheckRollup"] = [
                _status_context(item) for item in _extract_values(builds)
            ]
        return {field: available[field] for field in fields}

    @staticmethod
    def _belongs_to(repository: RepositoryRef, raw: Mapping[str, Any]) -> bool:
        project_key, repo_slug = _repository_identity(raw.get("toRef"))
        return (
            isinstance(project_key, str)
            and project_key.casefold() == repository.project_key.casefold()
            and repo_slug == repository.repo_slug
        )

    def _dashboard_pull_requests(self, repository: RepositoryRef, state: str) -> list[dict]:
        values: list[dict] = []
        start = 0
        while True:
            page = self.provider.list_dashboard_pull_requests(
                role="AUTHOR",
                state=state,
                start=start,
                limit=100,
            )
            values.extend(raw for raw in page if self._belongs_to(repository, raw))
            if len(page) < 100:
                return values
            start += 100

    def _matches(
        self,
        raw: Mapping[str, Any],
        query: Mapping[str, Any],
        me_ids: set[object],
    ) -> tuple[bool, dict[str, Any]]:
        title = str(raw.get("title") or "").casefold()
        body = str(raw.get("description") or "").casefold()
        searchable = [title if scope == "title" else body for scope in query["scopes"]]
        for term, negated in query["terms"]:
            matches = any(term in value for value in searchable)
            if matches == negated:
                return False, {}

        status_qualifiers: list[tuple[str, bool]] = []
        for key, value, negated in query["qualifiers"]:
            if key == "status":
                status_qualifiers.append((value, negated))
                continue
            if key == "state":
                matches = value in {"ALL", raw.get("state")}
            elif key == "author" and _same_text(value, "@me"):
                matches = raw.get("id") in me_ids
            elif key == "author":
                matches = _same_text(_author_login(raw), value)
            elif key == "base":
                to_ref = raw.get("toRef")
                branch = to_ref.get("displayId") if isinstance(to_ref, Mapping) else None
                matches = _same_text(branch, value)
            elif key == "head":
                matches = _head_matches(raw, value)
            else:
                matches = _review_matches(raw, value)
            if matches == negated:
                return False, {}

        if not status_qualifiers:
            return True, {}
        head_ref = raw.get("fromRef")
        head_sha = head_ref.get("latestCommit") if isinstance(head_ref, Mapping) else None
        builds = self.provider.list_associated_build_statuses(str(head_sha)) if head_sha else []
        statuses = [_status_context(item) for item in _extract_values(builds)]
        rollup_state = _rollup_state(statuses)
        for value, negated in status_qualifiers:
            if (rollup_state == value) == negated:
                return False, {"statusCheckRollup": statuses}
        return True, {"statusCheckRollup": statuses}

    def _page_pr_family(
        self,
        repository: RepositoryRef,
        raw: Mapping[str, Any],
        reader: Callable[..., list[dict]],
    ) -> list[dict]:
        values: list[dict] = []
        start = 0
        while True:
            page = reader(
                repository.project_key,
                repository.repo_slug,
                int(raw["id"]),
                start=start,
                limit=100,
            )
            values.extend(page)
            if len(page) < 100:
                return values
            start += 100

    def _diff_fields(self, repository: RepositoryRef, raw: Mapping[str, Any]) -> dict[str, Any]:
        changes = self._page_pr_family(
            repository,
            raw,
            self.provider.list_pull_request_changes,
        )
        diff = normalize_pull_request_diff(
            int(raw["id"]),
            self.provider.get_pull_request_diff_with_lines(
                repository.project_key,
                repository.repo_slug,
                int(raw["id"]),
            ),
        )
        line_counts: dict[str, tuple[int, int]] = {}
        for file_data in diff["files"]:
            additions = 0
            deletions = 0
            for hunk in file_data["hunks"]:
                for line in hunk.get("lines", []):
                    additions += line.get("type") == "ADDED"
                    deletions += line.get("type") == "REMOVED"
            line_counts[file_data["path"]] = (additions, deletions)

        files = []
        for change in changes:
            path = _path_to_string(change.get("path"))
            additions, deletions = line_counts.get(path, (0, 0))
            files.append(
                {
                    "path": path,
                    "additions": additions,
                    "deletions": deletions,
                    "changeType": _CHANGE_TYPE_MAP.get(
                        str(change.get("type") or "").upper(), "MODIFIED"
                    ),
                }
            )
        return {
            "additions": sum(item[0] for item in line_counts.values()),
            "deletions": sum(item[1] for item in line_counts.values()),
            "changedFiles": len(changes),
            "files": files,
        }

    def _activity_fields(self, repository: RepositoryRef, raw: Mapping[str, Any]) -> dict[str, Any]:
        activities = self._page_pr_family(
            repository,
            raw,
            self.provider.list_pull_request_activities,
        )
        activities.sort(key=lambda item: int(item.get("createdDate") or 0))
        comments: dict[object, dict] = {}
        for activity in activities:
            comment = activity.get("comment")
            action = activity.get("commentAction")
            if not isinstance(comment, dict) or action not in {"ADDED", "UPDATED", "DELETED"}:
                continue
            if action == "DELETED":
                comments.pop(comment.get("id"), None)
            else:
                comments[comment.get("id")] = comment
        mapped_comments = sorted(
            (_comment(item) for item in comments.values()),
            key=lambda item: item["createdAt"] or "",
        )

        merged = max(
            (item for item in activities if item.get("action") == "MERGED"),
            key=lambda item: int(item.get("createdDate") or 0),
            default=None,
        )
        return {
            "comments": mapped_comments,
            "mergedAt": _rfc3339(merged.get("createdDate")) if merged else None,
            "mergedBy": _user(merged.get("user")) if merged else None,
        }

    def _mergeability_fields(
        self, repository: RepositoryRef, raw: Mapping[str, Any]
    ) -> dict[str, str]:
        value = self.provider.get_pull_request_mergeability(
            repository.project_key,
            repository.repo_slug,
            int(raw["id"]),
        )
        if value.get("canMerge") is True:
            return {"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}
        if value.get("conflicted") is True:
            return {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}
        if value.get("vetoes"):
            return {"mergeable": "UNKNOWN", "mergeStateStatus": "BLOCKED"}
        return {"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"}
