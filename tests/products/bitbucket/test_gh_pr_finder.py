from datetime import UTC, datetime

import pytest

from atlassian_cli.core.errors import NotFoundError, ValidationError
from atlassian_cli.products.bitbucket.gh_compat import pr_finder
from atlassian_cli.products.bitbucket.gh_compat.pr_finder import PullRequestFinder
from atlassian_cli.products.bitbucket.gh_compat.repository_context import RepositoryResolution
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryRef,
    ServerIdentity,
)

SERVER = ServerIdentity.from_url("https://bitbucket.example.com")
REPO = RepositoryRef(SERVER, "DEMO", "example-repo")


def raw_pr(number: int, state: str, created: str, project: str, branch: str) -> dict:
    return {
        "id": number,
        "state": state,
        "createdDate": int(datetime.fromisoformat(created).replace(tzinfo=UTC).timestamp() * 1000),
        "fromRef": {
            "displayId": branch,
            "repository": {"slug": "example-repo", "project": {"key": project}},
        },
    }


class FakeProvider:
    def __init__(self, pages: dict[tuple[str, int], list[dict]] | None = None) -> None:
        self.pages = pages or {}
        self.calls: list[tuple] = []

    def list_pull_requests(self, project, repo, state, *, start, limit):
        self.calls.append((project, repo, state, start, limit))
        return self.pages.get((state, start), [])


def resolution(branch: str | None = "feature/DEMO-1234/example-change") -> RepositoryResolution:
    return RepositoryResolution(REPO, branch)


def test_numeric_selector_uses_resolved_repository_without_listing() -> None:
    provider = FakeProvider()
    result = PullRequestFinder(provider, SERVER).find("1234", resolution(), explicit_repo=False)
    assert result == PullRequestRef(REPO, 1234)
    assert provider.calls == []


def test_url_selector_is_authoritative_over_resolved_repository() -> None:
    selected = RepositoryRef(SERVER, "~example-user", "example-repo")
    url = "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"
    result = PullRequestFinder(FakeProvider(), SERVER).find(
        url,
        RepositoryResolution(selected, None),
        explicit_repo=True,
    )
    assert result == PullRequestRef(REPO, 1234)


def test_view_repo_without_selector_fails_before_current_branch_lookup() -> None:
    provider = FakeProvider()
    with pytest.raises(ValidationError, match="argument required when using the --repo flag"):
        PullRequestFinder(provider, SERVER).find(None, resolution(), explicit_repo=True)
    assert provider.calls == []


def test_branch_ranks_open_before_newer_closed_then_newest_open() -> None:
    provider = FakeProvider(
        {
            ("OPEN", 0): [
                raw_pr(
                    1233,
                    "OPEN",
                    "2026-07-14T12:00:00",
                    "DEMO",
                    "feature/DEMO-1234/example-change",
                ),
                raw_pr(
                    1234,
                    "OPEN",
                    "2026-07-15T12:00:00",
                    "DEMO",
                    "feature/DEMO-1234/example-change",
                ),
            ],
            ("DECLINED", 0): [
                raw_pr(
                    1235,
                    "DECLINED",
                    "2026-07-16T12:00:00",
                    "DEMO",
                    "feature/DEMO-1234/example-change",
                )
            ],
        }
    )
    result = PullRequestFinder(provider, SERVER).find(
        "feature/DEMO-1234/example-change",
        resolution(),
        explicit_repo=False,
    )
    assert result.number == 1234


def test_qualified_branch_requires_exact_source_project() -> None:
    provider = FakeProvider(
        {
            ("OPEN", 0): [
                raw_pr(
                    1234,
                    "OPEN",
                    "2026-07-15T12:00:00",
                    "DEMO",
                    "feature/DEMO-1234/example-change",
                ),
                raw_pr(
                    1235,
                    "OPEN",
                    "2026-07-16T12:00:00",
                    "~example-user",
                    "feature/DEMO-1234/example-change",
                ),
            ]
        }
    )
    result = PullRequestFinder(provider, SERVER).find(
        "~example-user:feature/DEMO-1234/example-change",
        resolution(),
        explicit_repo=False,
    )
    assert result.number == 1235


def test_detached_head_without_selector_is_not_found() -> None:
    with pytest.raises(NotFoundError, match="current branch"):
        PullRequestFinder(FakeProvider(), SERVER).find(
            None,
            resolution(None),
            explicit_repo=False,
        )


def test_branch_lookup_pages_each_state_until_a_short_page() -> None:
    first_page = [
        raw_pr(
            number,
            "OPEN",
            "2026-07-14T12:00:00",
            "DEMO",
            "feature/DEMO-1/example-change",
        )
        for number in range(1, 101)
    ]
    provider = FakeProvider(
        {
            ("OPEN", 0): first_page,
            ("OPEN", 100): [
                raw_pr(
                    1234,
                    "OPEN",
                    "2026-07-15T12:00:00",
                    "DEMO",
                    "feature/DEMO-1234/example-change",
                )
            ],
        }
    )

    result = PullRequestFinder(provider, SERVER).find(
        "feature/DEMO-1234/example-change",
        resolution(),
        explicit_repo=False,
    )

    assert result == PullRequestRef(REPO, 1234)
    assert provider.calls == [
        ("DEMO", "example-repo", "OPEN", 0, 100),
        ("DEMO", "example-repo", "OPEN", 100, 100),
        ("DEMO", "example-repo", "DECLINED", 0, 100),
        ("DEMO", "example-repo", "MERGED", 0, 100),
    ]


def test_duplicate_ids_are_ranked_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicate = raw_pr(
        1234,
        "OPEN",
        "2026-07-15T12:00:00",
        "DEMO",
        "feature/DEMO-1234/example-change",
    )
    provider = FakeProvider(
        {
            ("OPEN", 0): [duplicate],
            ("DECLINED", 0): [{**duplicate, "state": "DECLINED"}],
        }
    )
    ranked_ids: list[int] = []
    original_rank = pr_finder._rank

    def recording_rank(raw: dict) -> tuple[int, int, int]:
        ranked_ids.append(int(raw["id"]))
        return original_rank(raw)

    monkeypatch.setattr(pr_finder, "_rank", recording_rank)

    result = PullRequestFinder(provider, SERVER).find(
        "feature/DEMO-1234/example-change",
        resolution(),
        explicit_repo=False,
    )

    assert result == PullRequestRef(REPO, 1234)
    assert ranked_ids == [1234]


def test_branch_lookup_does_not_fall_back_to_fuzzy_ref_matching() -> None:
    provider = FakeProvider(
        {
            ("OPEN", 0): [
                raw_pr(
                    1234,
                    "OPEN",
                    "2026-07-15T12:00:00",
                    "DEMO",
                    "refs/heads/feature/DEMO-1234/example-change",
                )
            ]
        }
    )

    with pytest.raises(
        NotFoundError,
        match="no pull request found for branch feature/DEMO-1234/example-change",
    ):
        PullRequestFinder(provider, SERVER).find(
            "feature/DEMO-1234/example-change",
            resolution(),
            explicit_repo=False,
        )
