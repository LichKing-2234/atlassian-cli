import pytest

from atlassian_cli.core.errors import TransportError
from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.bitbucket.services.pr import PullRequestService


class FakePullRequestProvider:
    def __init__(self) -> None:
        self.approval_calls = []
        self.merge_calls = []

    def list_pull_requests(
        self,
        project_key: str,
        repo_slug: str,
        state: str,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> list[dict]:
        assert start >= 0
        assert limit > 0
        return [
            {
                "id": 42,
                "title": "Example pull request",
                "description": "Long body that should stay out of list output",
                "state": "OPEN",
                "open": True,
                "closed": False,
                "version": 7,
                "updatedDate": 1704153600000,
                "author": {"user": {"displayName": "Example Author", "name": "example-user-id"}},
                "participants": [{"user": {"displayName": "Code Owners"}}],
                "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
                "reviewers": [{"user": {"displayName": "reviewer-one"}, "approved": True}],
                "fromRef": {
                    "displayId": "feature/DEMO-1234/example-change",
                    "id": "refs/heads/feature/DEMO-1234/example-change",
                },
                "toRef": {"displayId": "main", "id": "refs/heads/main"},
            }
        ]

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return {
            "id": 42,
            "title": "Example pull request",
            "description": "Long body that should stay out of list output",
            "state": "OPEN",
            "open": True,
            "closed": False,
            "version": 7,
            "updatedDate": 1704153600000,
            "participants": [{"user": {"displayName": "Code Owners"}}],
            "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
            "reviewers": [{"user": {"displayName": "reviewer-one"}, "approved": True}],
            "fromRef": {"displayId": "feature/DEMO-1234/example-change"},
            "toRef": {"displayId": "main"},
        }

    def get_pull_request_diff(self, project_key: str, repo_slug: str, pr_id: int) -> str:
        return "--- a/e2e-note.txt\n+++ b/e2e-note.txt\n@@ -0,0 +1 @@\n+example change\n"

    def approve_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        self.approval_calls.append(("approve", project_key, repo_slug, pr_id))
        return {
            "approved": True,
            "status": "APPROVED",
            "role": "REVIEWER",
            "lastReviewedCommit": "abc123",
            "user": {"displayName": "Example Author", "name": "example-user-id"},
        }

    def unapprove_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        self.approval_calls.append(("unapprove", project_key, repo_slug, pr_id))
        return {
            "approved": False,
            "status": "UNAPPROVED",
            "role": "REVIEWER",
            "lastReviewedCommit": "abc123",
            "user": {"displayName": "Example Author", "name": "example-user-id"},
        }

    def merge_pull_request(
        self,
        project_key: str,
        repo_slug: str,
        pr_id: int,
        *,
        merge_message: str,
        pr_version: int | None,
    ) -> dict:
        self.merge_calls.append((project_key, repo_slug, pr_id, merge_message, pr_version))
        return {
            "id": pr_id,
            "title": "Example pull request",
            "state": "MERGED",
            "fromRef": {"displayId": "feature/DEMO-1234/example-change"},
            "toRef": {"displayId": "main"},
        }


def test_pull_request_service_normalizes_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get("DEMO", "example-skills", 42)

    assert result == {
        "id": 42,
        "title": "Example pull request",
        "description": "Long body that should stay out of list output",
        "state": "OPEN",
        "open": True,
        "closed": False,
        "updated_date": "1704153600000",
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "reviewers": [{"display_name": "reviewer-one", "approved": True}],
        "participants": [{"user": {"displayName": "Code Owners"}}],
        "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
    }


def test_pull_request_service_raises_clear_error_for_text_response() -> None:
    class TextPullRequestProvider(FakePullRequestProvider):
        def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> str:
            del project_key, repo_slug, pr_id
            return "<html>example response</html>"

    service = PullRequestService(provider=TextPullRequestProvider())

    with pytest.raises(TransportError, match="BitbucketPullRequest response"):
        service.get("DEMO", "example-repo", 42)


def test_pull_request_service_list_keeps_full_payload_for_machine_output() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.list("DEMO", "example-skills", "OPEN")

    assert result == {
        "results": [
            {
                "id": 42,
                "title": "Example pull request",
                "description": "Long body that should stay out of list output",
                "state": "OPEN",
                "open": True,
                "closed": False,
                "updated_date": "1704153600000",
                "author": {"display_name": "Example Author", "name": "example-user-id"},
                "reviewers": [{"display_name": "reviewer-one", "approved": True}],
                "from_ref": {
                    "display_id": "feature/DEMO-1234/example-change",
                    "id": "refs/heads/feature/DEMO-1234/example-change",
                },
                "to_ref": {"display_id": "main", "id": "refs/heads/main"},
                "participants": [{"user": {"displayName": "Code Owners"}}],
                "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }


def test_pull_request_service_list_accepts_start_and_limit() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.list("DEMO", "example-skills", "OPEN", start=25, limit=10)

    assert result["results"][0]["id"] == 42
    assert result["start_at"] == 25
    assert result["max_results"] == 10


def test_pull_request_service_list_page_returns_collection_page() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    page = service.list_page("DEMO", "example-skills", "OPEN", start=25, limit=10)

    assert isinstance(page, CollectionPage)
    assert page.start == 25
    assert page.limit == 10
    assert page.total is None
    assert page.items[0]["id"] == 42


def test_pull_request_service_exposes_raw_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get_raw("DEMO", "example-skills", 42)

    assert "version" in result


def test_pull_request_service_get_detail_includes_diff() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get_detail("DEMO", "example-skills", 42)

    assert result["id"] == 42
    assert result["title"] == "Example pull request"
    assert result["diff"].startswith("--- a/e2e-note.txt")
    assert "+example change" in result["diff"]


def test_pull_request_service_diff_with_lines_normalizes_provider_payload() -> None:
    class StructuredDiffProvider(FakePullRequestProvider):
        def get_pull_request_diff_with_lines(self, project_key: str, repo_slug: str, pr_id: int):
            return {
                "values": [
                    {
                        "destination": {"toString": "example.py"},
                        "hunks": [
                            {
                                "sourceLine": 0,
                                "sourceSpan": 0,
                                "destinationLine": 1,
                                "destinationSpan": 1,
                                "segments": [
                                    {
                                        "type": "ADDED",
                                        "lines": [
                                            {
                                                "destination": 1,
                                                "line": "+example response",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }

    service = PullRequestService(provider=StructuredDiffProvider())

    result = service.diff_with_lines("DEMO", "example-repo", 42)

    assert result["id"] == 42
    assert result["files"][0]["path"] == "example.py"
    assert result["files"][0]["hunks"][0]["lines"][0]["anchor"] == {
        "path": "example.py",
        "line": 1,
        "line_type": "ADDED",
    }


def test_pull_request_service_diff_with_lines_raw_preserves_provider_payload() -> None:
    raw_payload = {"values": [{"destination": {"toString": "example.py"}}]}

    class StructuredDiffProvider(FakePullRequestProvider):
        def get_pull_request_diff_with_lines(self, project_key: str, repo_slug: str, pr_id: int):
            return raw_payload

    service = PullRequestService(provider=StructuredDiffProvider())

    assert service.diff_with_lines_raw("DEMO", "example-repo", 42) is raw_payload


def test_pull_request_service_approve_normalizes_provider_payload() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.approve("DEMO", "example-repo", 42)

    assert result == {
        "approved": True,
        "status": "APPROVED",
        "role": "REVIEWER",
        "last_reviewed_commit": "abc123",
        "user": {"display_name": "Example Author", "name": "example-user-id"},
    }
    assert provider.approval_calls == [("approve", "DEMO", "example-repo", 42)]


def test_pull_request_service_unapprove_normalizes_provider_payload() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.unapprove("DEMO", "example-repo", 42)

    assert result == {
        "approved": False,
        "status": "UNAPPROVED",
        "role": "REVIEWER",
        "last_reviewed_commit": "abc123",
        "user": {"display_name": "Example Author", "name": "example-user-id"},
    }
    assert provider.approval_calls == [("unapprove", "DEMO", "example-repo", 42)]


def test_pull_request_service_approval_raw_methods_preserve_provider_payload() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    approved = service.approve_raw("DEMO", "example-repo", 42)
    unapproved = service.unapprove_raw("DEMO", "example-repo", 42)

    assert approved["status"] == "APPROVED"
    assert unapproved["status"] == "UNAPPROVED"
    assert provider.approval_calls == [
        ("approve", "DEMO", "example-repo", 42),
        ("unapprove", "DEMO", "example-repo", 42),
    ]


def test_pull_request_service_merge_prefetches_title_and_version() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.merge("DEMO", "example-repo", 42)

    assert result["state"] == "MERGED"
    assert provider.merge_calls == [
        ("DEMO", "example-repo", 42, "Merge pull request #42: Example pull request", 7)
    ]
