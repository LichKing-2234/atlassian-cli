import pytest

from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryRef,
    ServerIdentity,
)
from atlassian_cli.products.bitbucket.services.pr_read import (
    PullRequestListFilters,
    PullRequestReadService,
    parse_search_query,
)

SERVER = ServerIdentity.from_url("https://bitbucket.example.com")
REPO = RepositoryRef(SERVER, "DEMO", "example-repo")


def raw_pr(
    *,
    pr_id: int = 1234,
    title: str = "Example pull request",
    description: str = "example response",
    state: str = "OPEN",
    author: str = "~example-user",
    source_branch: str = "feature/DEMO-1234/example-change",
    target_branch: str = "DEMO",
) -> dict:
    repository = {
        "id": 101,
        "slug": "example-repo",
        "name": "example-repo",
        "project": {"id": 10, "key": "DEMO", "name": "DEMO"},
    }
    return {
        "id": pr_id,
        "title": title,
        "description": description,
        "state": state,
        "createdDate": 1784116800000,
        "updatedDate": 1784120400000,
        "author": {
            "user": {
                "id": 1001,
                "name": author,
                "displayName": "Example Author",
            }
        },
        "reviewers": [
            {
                "user": {
                    "id": 1002,
                    "name": "reviewer-one",
                    "displayName": "Example Collaborator",
                },
                "approved": False,
                "status": "UNAPPROVED",
            }
        ],
        "fromRef": {
            "displayId": source_branch,
            "latestCommit": "abc123",
            "repository": repository,
        },
        "toRef": {
            "displayId": target_branch,
            "latestCommit": "def456",
            "repository": repository,
        },
        "links": {
            "self": [
                {
                    "href": (
                        "https://bitbucket.example.com/projects/DEMO/repos/"
                        f"example-repo/pull-requests/{pr_id}"
                    )
                }
            ]
        },
    }


class FakeProvider:
    def __init__(
        self, pull_requests: list[dict], *, dashboard_pull_requests: list[dict] | None = None
    ) -> None:
        self.pull_requests = pull_requests
        self.dashboard_pull_requests = dashboard_pull_requests or []
        self.list_calls: list[tuple[str, int, int]] = []
        self.dashboard_calls: list[tuple[str, str, int, int]] = []
        self.auxiliary_calls: list[str] = []

    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        self.list_calls.append((state, start, limit))
        candidates = (
            self.pull_requests
            if state == "ALL"
            else [item for item in self.pull_requests if item["state"] == state]
        )
        return candidates[start : start + limit]

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return next(item for item in self.pull_requests if item["id"] == pr_id)

    def list_dashboard_pull_requests(
        self, *, role: str, state: str, start: int, limit: int
    ) -> list[dict]:
        self.dashboard_calls.append((role, state, start, limit))
        candidates = (
            self.dashboard_pull_requests
            if state == "ALL"
            else [item for item in self.dashboard_pull_requests if item["state"] == state]
        )
        return candidates[start : start + limit]

    def list_pull_request_changes(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        self.auxiliary_calls.append("changes")
        values = [{"type": "ADD", "path": {"toString": "example.py"}}]
        return values[start : start + limit]

    def get_pull_request_diff_with_lines(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict:
        self.auxiliary_calls.append("diff")
        return {
            "values": [
                {
                    "destination": {"toString": "example.py"},
                    "hunks": [
                        {
                            "segments": [
                                {
                                    "type": "ADDED",
                                    "lines": [{"destination": 1, "line": "+example response"}],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

    def list_pull_request_activities(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        self.auxiliary_calls.append("activities")
        values = [
            {
                "action": "COMMENTED",
                "commentAction": "ADDED",
                "comment": {
                    "id": 2001,
                    "text": "example comment",
                    "author": {
                        "id": 1002,
                        "name": "reviewer-one",
                        "displayName": "Example Collaborator",
                    },
                    "createdDate": 1784116800000,
                    "updatedDate": 1784116800000,
                },
            },
            {
                "action": "MERGED",
                "createdDate": 1784124000000,
                "user": {
                    "id": 1002,
                    "name": "reviewer-one",
                    "displayName": "Example Collaborator",
                },
            },
        ]
        return values[start : start + limit]

    def list_pull_request_commits(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int | None,
    ) -> list[dict]:
        self.auxiliary_calls.append("commits")
        values = [
            {
                "id": "abc123",
                "message": "Example issue summary\n\nexample response",
                "authorTimestamp": 1784116800000,
                "committerTimestamp": 1784120400000,
                "author": {
                    "id": 1001,
                    "name": "~example-user",
                    "displayName": "Example Author",
                },
            }
        ]
        return values[start : start + limit if limit is not None else None]

    def get_pull_request_mergeability(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        self.auxiliary_calls.append("mergeability")
        return {"canMerge": True, "conflicted": False, "vetoes": []}

    def list_associated_build_statuses(self, commit: str) -> list[dict]:
        self.auxiliary_calls.append("builds")
        return [
            {
                "key": "DEMO",
                "state": "SUCCESSFUL",
                "url": "https://ci.example.com/builds/1234",
                "dateAdded": 1784120400000,
            }
        ]


def test_basic_list_fields_do_not_trigger_auxiliary_reads() -> None:
    provider = FakeProvider([raw_pr()])
    service = PullRequestReadService(provider)

    result = service.list(
        REPO,
        PullRequestListFilters(state="open", limit=30),
        fields={"number", "title", "state", "url", "headRefName", "createdAt"},
    )

    assert result.items[0] == {
        "number": 1234,
        "title": "Example pull request",
        "state": "OPEN",
        "url": (
            "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"
        ),
        "headRefName": "feature/DEMO-1234/example-change",
        "createdAt": "2026-07-15T12:00:00Z",
    }
    assert provider.auxiliary_calls == []


def test_requested_enrichments_call_each_provider_family_once() -> None:
    provider = FakeProvider([raw_pr()])

    result = PullRequestReadService(provider).get(
        PullRequestRef(REPO, 1234),
        fields={
            "additions",
            "changedFiles",
            "comments",
            "commits",
            "deletions",
            "files",
            "mergeable",
            "mergeStateStatus",
            "mergedAt",
            "mergedBy",
            "statusCheckRollup",
        },
    )

    assert result["additions"] == 1
    assert result["deletions"] == 0
    assert result["changedFiles"] == 1
    assert result["mergeable"] == "MERGEABLE"
    assert result["mergeStateStatus"] == "CLEAN"
    assert result["statusCheckRollup"][0]["__typename"] == "StatusContext"
    assert provider.auxiliary_calls == [
        "changes",
        "diff",
        "activities",
        "commits",
        "mergeability",
        "builds",
    ]


def test_one_direct_field_returns_only_that_field() -> None:
    provider = FakeProvider([raw_pr()])

    result = PullRequestReadService(provider).get(PullRequestRef(REPO, 1234), {"title"})

    assert result == {"title": "Example pull request"}
    assert provider.auxiliary_calls == []


@pytest.mark.parametrize(
    ("state", "server_state"),
    [
        ("OPEN", "OPEN"),
        ("open", "OPEN"),
        ("DECLINED", "DECLINED"),
        ("declined", "DECLINED"),
        ("DeClInEd", "DECLINED"),
        ("MERGED", "MERGED"),
        ("all", "ALL"),
    ],
)
def test_list_normalizes_native_state_case_insensitively(state: str, server_state: str) -> None:
    provider = FakeProvider(
        [
            raw_pr(pr_id=1234, state="OPEN"),
            raw_pr(pr_id=1235, state="DECLINED"),
            raw_pr(pr_id=1236, state="MERGED"),
        ]
    )

    PullRequestReadService(provider).list(REPO, PullRequestListFilters(state=state), {"number"})

    assert provider.list_calls[0] == (server_state, 0, 100)


@pytest.mark.parametrize("query", ["state:closed", "is:closed", "state:draft"])
def test_search_rejects_non_native_states(query: str) -> None:
    with pytest.raises(ValueError, match="unsupported .* search value"):
        parse_search_query(query)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("state:DECLINED", "DECLINED"),
        ("state:declined", "DECLINED"),
        ("state:DeClInEd", "DECLINED"),
        ("is:MERGED", "MERGED"),
    ],
)
def test_search_accepts_native_states_case_insensitively(query: str, expected: str) -> None:
    parsed = parse_search_query(query)

    assert parsed["qualifiers"][0][1] == expected


def test_explicit_filters_combine_before_limit() -> None:
    matching = raw_pr()
    other = raw_pr(
        pr_id=1235,
        author="reviewer-two",
        source_branch="reviewer-two",
        target_branch="example-repo",
    )
    provider = FakeProvider([other, matching])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(
            limit=1,
            author="~example-user",
            base="DEMO",
            head="feature/DEMO-1234/example-change",
        ),
        {"number"},
    )

    assert result.items == [{"number": 1234}]


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ('"Example pull" in:title', [1234]),
        ('"Example pull" in:body', [1235]),
        ("example", [1234, 1235]),
    ],
)
def test_search_supports_quoted_text_and_in_scopes(search: str, expected: list[int]) -> None:
    provider = FakeProvider(
        [
            raw_pr(pr_id=1234, title="Example pull request", description="example response"),
            raw_pr(pr_id=1235, title="Example issue summary", description="Example pull body"),
        ]
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search=search),
        {"number"},
    )

    assert [item["number"] for item in result.items] == expected


def test_search_combines_positive_and_negative_qualifiers() -> None:
    required = raw_pr()
    approved = raw_pr(pr_id=1235, source_branch="reviewer-two")
    approved["reviewers"][0].update({"approved": True, "status": "APPROVED"})
    provider = FakeProvider([required, approved])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(
            search=("state:open author:~example-user base:DEMO review:required -head:reviewer-two")
        ),
        {"number"},
    )

    assert result.items == [{"number": 1234}]


def test_search_state_replaces_only_the_default_open_state() -> None:
    provider = FakeProvider([raw_pr(pr_id=1234, state="OPEN"), raw_pr(pr_id=1235, state="MERGED")])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search="state:merged"),
        {"number"},
    )

    assert result.items == [{"number": 1235}]
    assert provider.list_calls[0] == ("ALL", 0, 100)


def test_nondefault_state_remains_an_additional_search_predicate() -> None:
    provider = FakeProvider(
        [raw_pr(pr_id=1234, state="OPEN"), raw_pr(pr_id=1235, state="DECLINED")]
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(state="DECLINED", search="state:OPEN"),
        {"number"},
    )

    assert result.items == []
    assert provider.list_calls[0] == ("DECLINED", 0, 100)


def test_status_search_enriches_only_when_status_is_required() -> None:
    provider = FakeProvider([raw_pr()])
    service = PullRequestReadService(provider)

    without_status = service.list(REPO, PullRequestListFilters(), {"number"})
    assert without_status.items == [{"number": 1234}]
    assert provider.auxiliary_calls == []

    with_status = service.list(
        REPO,
        PullRequestListFilters(search="status:success"),
        {"number"},
    )
    assert with_status.items == [{"number": 1234}]
    assert provider.auxiliary_calls == ["builds"]


def test_pagination_applies_filters_before_limit_and_preserves_order() -> None:
    pull_requests = [raw_pr(pr_id=2000 + index, author="reviewer-two") for index in range(100)] + [
        raw_pr(pr_id=3000 + index, author="~example-user") for index in range(3)
    ]
    provider = FakeProvider(pull_requests)

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(limit=3, author="~example-user"),
        {"number"},
    )

    assert result.items == [{"number": 3000}, {"number": 3001}, {"number": 3002}]
    assert provider.list_calls == [("OPEN", 0, 100), ("OPEN", 100, 100)]


def test_count_total_continues_paging_but_retains_only_the_limit() -> None:
    provider = FakeProvider([raw_pr(pr_id=2000 + index) for index in range(130)])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(limit=30),
        {"number"},
        count_total=True,
    )

    assert len(result.items) == 30
    assert result.total_count == 130
    assert provider.list_calls == [("OPEN", 0, 100), ("OPEN", 100, 100)]


def test_list_deduplicates_ids_without_reordering() -> None:
    pull_requests = [raw_pr(pr_id=2000 + index) for index in range(100)]
    pull_requests.extend([raw_pr(pr_id=2099), raw_pr(pr_id=2100)])
    provider = FakeProvider(pull_requests)

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(limit=101),
        {"number"},
        count_total=True,
    )

    assert [item["number"] for item in result.items] == list(range(2000, 2101))
    assert result.total_count == 101


def test_author_me_uses_dashboard_and_filters_to_the_resolved_repository() -> None:
    matching = raw_pr(pr_id=1234)
    other_repository = raw_pr(pr_id=1235)
    other_repository["toRef"]["repository"]["project"]["key"] = "~example-user"
    provider = FakeProvider(
        [matching],
        dashboard_pull_requests=[other_repository, matching],
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(author="@me"),
        {"number"},
    )

    assert result.items == [{"number": 1234}]
    assert provider.dashboard_calls == [("AUTHOR", "OPEN", 0, 100)]
    assert provider.list_calls == []


@pytest.mark.parametrize(
    ("project_key", "repo_slug", "expected"),
    [
        ("demo", "example-repo", [1234]),
        ("~example-user", "example-repo", []),
        ("DEMO", "Example-repo", []),
    ],
)
def test_dashboard_repository_match_casefolds_only_the_project_key(
    project_key: str,
    repo_slug: str,
    expected: list[int],
) -> None:
    dashboard_pull_request = raw_pr()
    repository = dashboard_pull_request["toRef"]["repository"]
    repository["project"]["key"] = project_key
    repository["slug"] = repo_slug
    provider = FakeProvider([], dashboard_pull_requests=[dashboard_pull_request])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(author="@me"),
        {"number"},
    )

    assert [item["number"] for item in result.items] == expected
    assert provider.dashboard_calls == [("AUTHOR", "OPEN", 0, 100)]


def test_author_me_with_explicit_all_state_keeps_all_service_semantics() -> None:
    open_pull_request = raw_pr(pr_id=1234, state="OPEN")
    merged_pull_request = raw_pr(pr_id=1235, state="MERGED")
    other_repository = raw_pr(pr_id=1236, state="MERGED")
    other_repository["toRef"]["repository"]["project"]["key"] = "~example-user"
    provider = FakeProvider(
        [open_pull_request, merged_pull_request],
        dashboard_pull_requests=[open_pull_request, other_repository, merged_pull_request],
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(state="all", author="@me"),
        {"number"},
    )

    assert result.items == [{"number": 1234}, {"number": 1235}]
    assert provider.dashboard_calls == [("AUTHOR", "ALL", 0, 100)]
    assert provider.list_calls == []


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("author:@me state:merged", [1235]),
        ("author:@me -state:open", [1235]),
    ],
)
def test_author_me_search_state_qualifiers_fetch_all_dashboard_states(
    search: str, expected: list[int]
) -> None:
    provider = FakeProvider(
        [raw_pr(pr_id=1234, state="OPEN"), raw_pr(pr_id=1235, state="MERGED")],
        dashboard_pull_requests=[
            raw_pr(pr_id=1234, state="OPEN"),
            raw_pr(pr_id=1235, state="MERGED"),
        ],
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search=search),
        {"number"},
    )

    assert [item["number"] for item in result.items] == expected
    assert provider.dashboard_calls == [("AUTHOR", "ALL", 0, 100)]
    assert provider.list_calls == []


def test_negated_author_me_with_state_search_uses_all_dashboard_states() -> None:
    authored_by_me = raw_pr(pr_id=1234, state="MERGED", author="~example-user")
    authored_by_collaborator = raw_pr(pr_id=1235, state="MERGED", author="reviewer-two")
    open_pull_request = raw_pr(pr_id=1236, state="OPEN", author="reviewer-two")
    provider = FakeProvider(
        [authored_by_me, authored_by_collaborator, open_pull_request],
        dashboard_pull_requests=[authored_by_me],
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search="-author:@me state:merged"),
        {"number"},
    )

    assert result.items == [{"number": 1235}]
    assert provider.dashboard_calls == [("AUTHOR", "ALL", 0, 100)]
    assert provider.list_calls == [("ALL", 0, 100)]


@pytest.mark.parametrize(
    "qualifier",
    [
        f"{negated}{key}:{value}"
        for key, value in [
            ("assignee", "example-user-id"),
            ("draft", "DEMO"),
            ("label", "DEMO"),
            ("milestone", "DEMO"),
            ("project", "DEMO"),
            ("app", "DEMO"),
            ("team", "DEMO"),
        ]
        for negated in ("", "-")
    ],
)
def test_n03_search_qualifiers_are_rejected_before_provider_calls(qualifier: str) -> None:
    provider = FakeProvider([raw_pr()])

    with pytest.raises(ValueError, match="unsupported search qualifier"):
        PullRequestReadService(provider).list(
            REPO,
            PullRequestListFilters(search=qualifier),
            {"number"},
        )

    assert provider.list_calls == []
    assert provider.dashboard_calls == []


def test_invalid_limit_is_rejected_before_provider_calls() -> None:
    provider = FakeProvider([raw_pr()])

    with pytest.raises(ValueError, match="greater than zero"):
        PullRequestReadService(provider).list(
            REPO,
            PullRequestListFilters(limit=0),
            {"number"},
        )

    assert provider.list_calls == []


def test_direct_projection_maps_every_supported_direct_field() -> None:
    provider = FakeProvider([raw_pr()])
    fields = {
        "author",
        "baseRefName",
        "baseRefOid",
        "body",
        "closed",
        "closedAt",
        "createdAt",
        "fullDatabaseId",
        "headRefName",
        "headRefOid",
        "headRepository",
        "headRepositoryOwner",
        "id",
        "isCrossRepository",
        "number",
        "reviewDecision",
        "reviewRequests",
        "state",
        "title",
        "updatedAt",
        "url",
    }
    result = PullRequestReadService(provider).get(PullRequestRef(REPO, 1234), fields)

    assert result == {
        "author": {
            "id": "1001",
            "is_bot": False,
            "login": "~example-user",
            "name": "Example Author",
        },
        "baseRefName": "DEMO",
        "baseRefOid": "def456",
        "body": "example response",
        "closed": False,
        "closedAt": None,
        "createdAt": "2026-07-15T12:00:00Z",
        "fullDatabaseId": "1234",
        "headRefName": "feature/DEMO-1234/example-change",
        "headRefOid": "abc123",
        "headRepository": {
            "id": "101",
            "name": "example-repo",
            "nameWithOwner": "DEMO/example-repo",
        },
        "headRepositoryOwner": {"id": "10", "login": "DEMO", "name": "DEMO"},
        "id": "1234",
        "isCrossRepository": False,
        "number": 1234,
        "reviewDecision": "REVIEW_REQUIRED",
        "reviewRequests": [
            {
                "id": "1002",
                "is_bot": False,
                "login": "reviewer-one",
                "name": "Example Collaborator",
            }
        ],
        "state": "OPEN",
        "title": "Example pull request",
        "updatedAt": "2026-07-15T13:00:00Z",
        "url": (
            "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"
        ),
    }


def test_presenter_reviewers_include_all_statuses_without_changing_public_requests() -> None:
    pull_request = raw_pr()
    approved = {
        "user": {
            "id": 1003,
            "name": "reviewer-two",
            "displayName": "reviewer-two",
        },
        "approved": True,
        "status": "APPROVED",
    }
    needs_work = {
        "user": {
            "id": 1004,
            "name": "reviewer-three",
            "displayName": "reviewer-three",
        },
        "approved": False,
        "status": "NEEDS_WORK",
    }
    pull_request["reviewers"].extend([approved, needs_work])

    result = PullRequestReadService(FakeProvider([pull_request])).get(
        PullRequestRef(REPO, 1234),
        {"reviewRequests", "_reviewers"},
    )

    assert [reviewer["login"] for reviewer in result["reviewRequests"]] == [
        "reviewer-one",
        "reviewer-three",
    ]
    assert [
        (reviewer["user"]["login"], reviewer["status"]) for reviewer in result["_reviewers"]
    ] == [
        ("reviewer-one", "UNAPPROVED"),
        ("reviewer-two", "APPROVED"),
        ("reviewer-three", "NEEDS_WORK"),
    ]


def test_direct_projection_uses_slug_user_fallback_and_closed_date() -> None:
    pull_request = raw_pr(state="DECLINED")
    pull_request["closedDate"] = 1784124000000
    pull_request["author"] = {"user": {"id": 1001, "slug": "~example-user"}}
    pull_request["fromRef"]["repository"] = {
        "id": 102,
        "slug": "example-repo",
        "name": "example-repo",
        "project": {"id": 11, "key": "~example-user", "name": "~example-user"},
    }
    provider = FakeProvider([pull_request])

    result = PullRequestReadService(provider).get(
        PullRequestRef(REPO, 1234),
        {"author", "closed", "closedAt", "isCrossRepository", "state"},
    )

    assert result == {
        "author": {
            "id": "1001",
            "is_bot": False,
            "login": "~example-user",
            "name": "~example-user",
        },
        "closed": True,
        "closedAt": "2026-07-15T14:00:00Z",
        "isCrossRepository": True,
        "state": "DECLINED",
    }


class DetailedEnrichmentProvider(FakeProvider):
    def list_pull_request_changes(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        self.auxiliary_calls.append("changes")
        values = [
            {"type": change_type, "path": {"toString": path}}
            for change_type, path in [
                ("ADD", "DEMO"),
                ("DELETE", "DEMO-1"),
                ("MOVE", "DEMO-1234"),
                ("COPY", "example-repo"),
                ("MODIFY", "example.py"),
            ]
        ]
        return values[start : start + limit]

    def get_pull_request_diff_with_lines(
        self, project_key: str, repo_slug: str, pr_id: int
    ) -> dict:
        self.auxiliary_calls.append("diff")
        return {
            "values": [
                {
                    "destination": {"toString": "DEMO"},
                    "hunks": [
                        {
                            "segments": [
                                {
                                    "type": "ADDED",
                                    "lines": [
                                        {"destination": 1, "line": "+example response"},
                                        {"destination": 2, "line": "+example comment"},
                                    ],
                                },
                                {
                                    "type": "REMOVED",
                                    "lines": [{"source": 1, "line": "-example response"}],
                                },
                            ]
                        }
                    ],
                }
            ]
        }

    def list_pull_request_activities(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        start: int,
        limit: int,
    ) -> list[dict]:
        self.auxiliary_calls.append("activities")
        user = {
            "id": 1002,
            "name": "reviewer-one",
            "displayName": "Example Collaborator",
        }
        values = [
            {
                "action": "MERGED",
                "createdDate": 1784116800000,
                "user": user,
            },
            {
                "action": "COMMENTED",
                "commentAction": "UPDATED",
                "createdDate": 1784120400000,
                "comment": {
                    "id": 2001,
                    "text": "example response",
                    "author": user,
                    "createdDate": 1784116800000,
                    "updatedDate": 1784120400000,
                },
            },
            {
                "action": "COMMENTED",
                "commentAction": "ADDED",
                "createdDate": 1784116800000,
                "comment": {
                    "id": 2001,
                    "text": "example comment",
                    "author": user,
                    "createdDate": 1784116800000,
                    "updatedDate": 1784116800000,
                },
            },
            {
                "action": "COMMENTED",
                "commentAction": "ADDED",
                "createdDate": 1784120400000,
                "comment": {
                    "id": 2002,
                    "text": "example comment",
                    "author": user,
                    "createdDate": 1784120400000,
                    "updatedDate": 1784120400000,
                },
            },
            {
                "action": "COMMENTED",
                "commentAction": "DELETED",
                "createdDate": 1784124000000,
                "comment": {"id": 2002},
            },
            {
                "action": "MERGED",
                "createdDate": 1784124000000,
                "user": user,
            },
        ]
        return values[start : start + limit]


def test_enrichment_maps_diff_comment_commit_and_build_objects() -> None:
    provider = DetailedEnrichmentProvider([raw_pr()])

    result = PullRequestReadService(provider).get(
        PullRequestRef(REPO, 1234),
        {
            "additions",
            "changedFiles",
            "comments",
            "commits",
            "deletions",
            "files",
            "mergedAt",
            "mergedBy",
            "statusCheckRollup",
        },
    )

    assert result["additions"] == 2
    assert result["deletions"] == 1
    assert result["changedFiles"] == 5
    assert [item["changeType"] for item in result["files"]] == [
        "ADDED",
        "DELETED",
        "RENAMED",
        "COPIED",
        "MODIFIED",
    ]
    assert result["files"][0] == {
        "path": "DEMO",
        "additions": 2,
        "deletions": 1,
        "changeType": "ADDED",
    }
    assert [comment["body"] for comment in result["comments"]] == ["example response"]
    assert result["comments"][0]["updatedAt"] == "2026-07-15T13:00:00Z"
    assert result["mergedAt"] == "2026-07-15T14:00:00Z"
    assert result["mergedBy"]["login"] == "reviewer-one"
    assert result["commits"][0] == {
        "oid": "abc123",
        "messageHeadline": "Example issue summary",
        "messageBody": "\nexample response",
        "authoredDate": "2026-07-15T12:00:00Z",
        "committedDate": "2026-07-15T13:00:00Z",
        "authors": [
            {
                "id": "1001",
                "is_bot": False,
                "login": "~example-user",
                "name": "Example Author",
            }
        ],
    }
    assert result["statusCheckRollup"] == [
        {
            "__typename": "StatusContext",
            "context": "DEMO",
            "state": "SUCCESS",
            "targetUrl": "https://ci.example.com/builds/1234",
            "startedAt": "2026-07-15T13:00:00Z",
        }
    ]


@pytest.mark.parametrize(
    ("payload", "mergeable", "merge_state"),
    [
        ({"canMerge": True, "conflicted": False, "vetoes": []}, "MERGEABLE", "CLEAN"),
        ({"canMerge": False, "conflicted": True, "vetoes": []}, "CONFLICTING", "DIRTY"),
        (
            {"canMerge": False, "conflicted": False, "vetoes": [{"summaryMessage": "DEMO"}]},
            "UNKNOWN",
            "BLOCKED",
        ),
        ({"canMerge": False, "conflicted": False, "vetoes": []}, "UNKNOWN", "UNKNOWN"),
    ],
)
def test_mergeability_mapping(payload: dict, mergeable: str, merge_state: str) -> None:
    class MergeabilityProvider(FakeProvider):
        def get_pull_request_mergeability(
            self, project_key: str, repo_slug: str, pr_id: int
        ) -> dict:
            self.auxiliary_calls.append("mergeability")
            return payload

    provider = MergeabilityProvider([raw_pr()])

    result = PullRequestReadService(provider).get(
        PullRequestRef(REPO, 1234), {"mergeable", "mergeStateStatus"}
    )

    assert result == {"mergeable": mergeable, "mergeStateStatus": merge_state}
    assert provider.auxiliary_calls == ["mergeability"]


def test_empty_build_response_returns_empty_rollup_for_resolved_head() -> None:
    class EmptyBuildProvider(FakeProvider):
        def list_associated_build_statuses(self, commit: str) -> list[dict]:
            self.auxiliary_calls.append(f"builds:{commit}")
            return []

    provider = EmptyBuildProvider([raw_pr()])

    result = PullRequestReadService(provider).get(PullRequestRef(REPO, 1234), {"statusCheckRollup"})

    assert result == {"statusCheckRollup": []}
    assert provider.auxiliary_calls == ["builds:abc123"]


def test_search_status_reuses_build_enrichment_for_projection() -> None:
    provider = FakeProvider([raw_pr()])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search="status:success"),
        {"number", "statusCheckRollup"},
    )

    assert result.items[0]["statusCheckRollup"][0]["state"] == "SUCCESS"
    assert provider.auxiliary_calls == ["builds"]


def test_each_paged_enrichment_family_reads_until_a_short_page() -> None:
    class PagedEnrichmentProvider(FakeProvider):
        def list_pull_request_changes(
            self,
            project_key: str,
            repo_slug: str,
            pr_id: int,
            *,
            start: int,
            limit: int,
        ) -> list[dict]:
            self.auxiliary_calls.append(f"changes:{start}")
            values = [{"type": "MODIFY", "path": {"toString": "example.py"}} for _ in range(101)]
            return values[start : start + limit]

        def list_pull_request_activities(
            self,
            project_key: str,
            repo_slug: str,
            pr_id: int,
            *,
            start: int,
            limit: int,
        ) -> list[dict]:
            self.auxiliary_calls.append(f"activities:{start}")
            values = [{"action": "OPENED", "createdDate": index} for index in range(101)]
            return values[start : start + limit]

        def list_pull_request_commits(
            self,
            project_key: str,
            repo_slug: str,
            pr_id: int,
            *,
            start: int,
            limit: int | None,
        ) -> list[dict]:
            self.auxiliary_calls.append(f"commits:{start}")
            values = [{"id": "abc123"} for _ in range(101)]
            return values[start : start + limit if limit is not None else None]

        def get_pull_request_diff_with_lines(
            self, project_key: str, repo_slug: str, pr_id: int
        ) -> dict:
            self.auxiliary_calls.append("diff")
            return {"values": []}

    provider = PagedEnrichmentProvider([raw_pr()])

    result = PullRequestReadService(provider).get(
        PullRequestRef(REPO, 1234), {"changedFiles", "comments", "commits"}
    )

    assert result["changedFiles"] == 101
    assert len(result["commits"]) == 101
    assert provider.auxiliary_calls == [
        "changes:0",
        "changes:100",
        "diff",
        "activities:0",
        "activities:100",
        "commits:0",
        "commits:100",
    ]


def test_dashboard_paging_does_not_stop_on_a_page_filtered_to_other_repositories() -> None:
    other_repository_items = []
    for index in range(100):
        item = raw_pr(pr_id=2000 + index)
        item["toRef"]["repository"]["project"]["key"] = "~example-user"
        other_repository_items.append(item)
    matching = raw_pr(pr_id=1234)
    provider = FakeProvider(
        [matching],
        dashboard_pull_requests=[*other_repository_items, matching],
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search="author:@me"),
        {"number"},
    )

    assert result.items == [{"number": 1234}]
    assert provider.dashboard_calls == [
        ("AUTHOR", "OPEN", 0, 100),
        ("AUTHOR", "OPEN", 100, 100),
    ]


@pytest.mark.parametrize("qualifier", ["-state:open", "-is:open"])
def test_negated_search_state_overrides_the_default_open(qualifier: str) -> None:
    provider = FakeProvider([raw_pr(pr_id=1234, state="OPEN"), raw_pr(pr_id=1235, state="MERGED")])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search=qualifier),
        {"number"},
    )

    assert result.items == [{"number": 1235}]
    assert provider.list_calls[0] == ("ALL", 0, 100)


@pytest.mark.parametrize(
    ("review", "expected"),
    [
        ("none", 1234),
        ("required", 1235),
        ("approved", 1236),
        ("changes_requested", 1237),
    ],
)
def test_search_maps_each_review_value(review: str, expected: int) -> None:
    none = raw_pr(pr_id=1234)
    none["reviewers"] = []
    required = raw_pr(pr_id=1235)
    approved = raw_pr(pr_id=1236)
    approved["reviewers"][0].update({"approved": True, "status": "APPROVED"})
    changes_requested = raw_pr(pr_id=1237)
    changes_requested["reviewers"][0]["status"] = "NEEDS_WORK"
    provider = FakeProvider([none, required, approved, changes_requested])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search=f"review:{review}"),
        {"number"},
    )

    assert result.items == [{"number": expected}]


@pytest.mark.parametrize(
    ("status", "expected"),
    [("success", 1234), ("pending", 1235), ("failure", 1236)],
)
def test_search_maps_each_status_value(status: str, expected: int) -> None:
    class StatusProvider(FakeProvider):
        def list_associated_build_statuses(self, commit: str) -> list[dict]:
            self.auxiliary_calls.append(f"builds:{commit}")
            return [
                {
                    "key": "DEMO",
                    "state": {
                        "DEMO": "SUCCESSFUL",
                        "DEMO-1": "INPROGRESS",
                        "DEMO-1234": "FAILED",
                    }[commit],
                }
            ]

    successful = raw_pr(pr_id=1234)
    successful["fromRef"]["latestCommit"] = "DEMO"
    pending = raw_pr(pr_id=1235)
    pending["fromRef"]["latestCommit"] = "DEMO-1"
    failure = raw_pr(pr_id=1236)
    failure["fromRef"]["latestCommit"] = "DEMO-1234"
    provider = StatusProvider([successful, pending, failure])

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search=f"status:{status}"),
        {"number"},
    )

    assert result.items == [{"number": expected}]
    assert provider.auxiliary_calls == ["builds:DEMO", "builds:DEMO-1", "builds:DEMO-1234"]


def test_negated_author_me_uses_dashboard_ids_to_filter_repository_list() -> None:
    authored_by_me = raw_pr(pr_id=1234, author="~example-user")
    authored_by_collaborator = raw_pr(pr_id=1235, author="reviewer-two")
    provider = FakeProvider(
        [authored_by_me, authored_by_collaborator],
        dashboard_pull_requests=[authored_by_me],
    )

    result = PullRequestReadService(provider).list(
        REPO,
        PullRequestListFilters(search="-author:@me"),
        {"number"},
    )

    assert result.items == [{"number": 1235}]
    assert provider.dashboard_calls == [("AUTHOR", "OPEN", 0, 100)]
    assert provider.list_calls == [("OPEN", 0, 100)]
