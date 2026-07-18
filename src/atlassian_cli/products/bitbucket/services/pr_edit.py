from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from atlassian_cli.core.errors import TransportError
from atlassian_cli.products.bitbucket.gh_compat.selectors import PullRequestRef
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider


@dataclass(frozen=True)
class PullRequestEdits:
    title: str | None = None
    body: str | None = None
    base: str | None = None
    add_reviewers: tuple[str, ...] = ()
    remove_reviewers: tuple[str, ...] = ()

    def dirty(self) -> bool:
        return any(value is not None for value in (self.title, self.body, self.base)) or bool(
            self.add_reviewers or self.remove_reviewers
        )


def _reviewer_login(reviewer: object) -> str | None:
    if not isinstance(reviewer, Mapping):
        return None
    user = reviewer.get("user")
    if not isinstance(user, Mapping):
        return None
    for key in ("name", "slug", "username"):
        value = user.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def reviewer_logins(raw: Mapping) -> tuple[str, ...]:
    reviewers = raw.get("reviewers")
    if not isinstance(reviewers, list):
        return ()
    return tuple(
        login
        for reviewer in reviewers
        for login in [_reviewer_login(reviewer)]
        if login is not None
    )


def _updated_reviewers(current: Mapping, edits: PullRequestEdits) -> list[object]:
    raw_reviewers = current.get("reviewers")
    reviewers = raw_reviewers if isinstance(raw_reviewers, list) else []
    removals = set(edits.remove_reviewers)
    retained: list[object] = []
    retained_logins: set[str] = set()

    for reviewer in reviewers:
        login = _reviewer_login(reviewer)
        if login is not None and login in removals:
            continue
        retained.append(deepcopy(reviewer))
        if login is not None:
            retained_logins.add(login)

    for login in edits.add_reviewers:
        if login in removals or login in retained_logins:
            continue
        retained.append({"user": {"name": login}})
        retained_logins.add(login)
    return retained


def _updated_destination(current: Mapping, base: str | None) -> dict:
    destination = current.get("toRef")
    if not isinstance(destination, Mapping):
        raise TransportError("invalid Bitbucket pull request destination ref")
    updated = deepcopy(dict(destination))
    if base is not None:
        display_id = base.removeprefix("refs/heads/")
        updated["id"] = f"refs/heads/{display_id}"
        updated["displayId"] = display_id
    return updated


def build_update_payload(current: Mapping, edits: PullRequestEdits) -> dict:
    version = current.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise TransportError("invalid Bitbucket pull request version")
    source = current.get("fromRef")
    if not isinstance(source, Mapping):
        raise TransportError("invalid Bitbucket pull request source ref")

    return {
        "version": version,
        "title": current.get("title", "") if edits.title is None else edits.title,
        "description": (current.get("description", "") if edits.body is None else edits.body),
        "fromRef": deepcopy(dict(source)),
        "toRef": _updated_destination(current, edits.base),
        "reviewers": _updated_reviewers(current, edits),
    }


class PullRequestEditService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def load(self, ref: PullRequestRef) -> dict:
        raw = self.provider.get_pull_request(
            ref.repository.project_key,
            ref.repository.repo_slug,
            ref.number,
        )
        if not isinstance(raw, dict):
            raise TransportError("invalid Bitbucket pull request response")
        return raw

    def edit(
        self,
        ref: PullRequestRef,
        edits: PullRequestEdits,
        *,
        current: dict | None = None,
    ) -> dict:
        current = self.load(ref) if current is None else current
        payload = build_update_payload(current, edits)
        updated = self.provider.update_pull_request(
            ref.repository.project_key,
            ref.repository.repo_slug,
            ref.number,
            payload,
        )
        if not isinstance(updated, dict):
            raise TransportError("invalid Bitbucket pull request update response")
        return updated
