from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.bitbucket.services.pr import PullRequestService


class FakePullRequestProvider:
    def __init__(self) -> None:
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
                "author": {"user": {"displayName": "Alice", "name": "alice@example.com"}},
                "participants": [{"user": {"displayName": "Code Owners"}}],
                "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
                "reviewers": [{"user": {"displayName": "Bob"}, "approved": True}],
                "fromRef": {"displayId": "feature/output", "id": "refs/heads/feature/output"},
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
            "reviewers": [{"user": {"displayName": "Bob"}, "approved": True}],
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
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
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
        }


def test_pull_request_service_normalizes_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get("PROJ", "example-skills", 42)

    assert result == {
        "id": 42,
        "title": "Example pull request",
        "description": "Long body that should stay out of list output",
        "state": "OPEN",
        "open": True,
        "closed": False,
        "updated_date": "1704153600000",
        "from_ref": {"display_id": "feature/output"},
        "to_ref": {"display_id": "main"},
        "reviewers": [{"display_name": "Bob", "approved": True}],
        "participants": [{"user": {"displayName": "Code Owners"}}],
        "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
    }


def test_pull_request_service_list_keeps_full_payload_for_machine_output() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.list("PROJ", "example-skills", "OPEN")

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
                "author": {"display_name": "Alice", "name": "alice@example.com"},
                "reviewers": [{"display_name": "Bob", "approved": True}],
                "from_ref": {"display_id": "feature/output", "id": "refs/heads/feature/output"},
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

    result = service.list("PROJ", "example-skills", "OPEN", start=25, limit=10)

    assert result["results"][0]["id"] == 42
    assert result["start_at"] == 25
    assert result["max_results"] == 10


def test_pull_request_service_list_page_returns_collection_page() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    page = service.list_page("PROJ", "example-skills", "OPEN", start=25, limit=10)

    assert isinstance(page, CollectionPage)
    assert page.start == 25
    assert page.limit == 10
    assert page.total is None
    assert page.items[0]["id"] == 42


def test_pull_request_service_exposes_raw_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get_raw("PROJ", "example-skills", 42)

    assert "version" in result


def test_pull_request_service_merge_prefetches_title_and_version() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.merge("PROJ", "infra", 42)

    assert result["state"] == "MERGED"
    assert provider.merge_calls == [
        ("PROJ", "infra", 42, "Merge pull request #42: Example pull request", 7)
    ]
