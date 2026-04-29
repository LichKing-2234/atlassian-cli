from atlassian_cli.output.interactive import CollectionPage
from atlassian_cli.products.jira.services.issue import IssueService


class FakeIssueProvider:
    def __init__(self) -> None:
        self.get_issue_calls = 0

    def get_issue(self, issue_key: str) -> dict:
        self.get_issue_calls += 1
        return {
            "key": issue_key,
            "fields": {
                "summary": "Example issue summary",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Example Author"},
                "reporter": {"displayName": "reviewer-one"},
                "priority": {"name": "High"},
                "updated": "2026-04-19T09:00:00.000+0000",
            },
        }

    def search_issues(self, jql: str, start: int, limit: int) -> dict:
        assert jql == "project = DEMO"
        assert start == 0
        assert limit == 2
        return {
            "total": 2,
            "startAt": start,
            "maxResults": limit,
            "issues": [
                {
                    "key": "DEMO-1",
                    "fields": {
                        "summary": "Example issue summary",
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Example Author"},
                        "reporter": {"displayName": "reviewer-one"},
                        "priority": {"name": "High"},
                        "updated": "2026-04-19T09:00:00.000+0000",
                    },
                },
                {
                    "key": "DEMO-2",
                    "fields": {
                        "summary": "Example follow-up",
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "reviewer-two"},
                        "reporter": {"displayName": "reviewer-one"},
                        "priority": {"name": "Medium"},
                        "updated": "2026-04-20T09:00:00.000+0000",
                    },
                },
            ],
        }


def test_issue_service_normalizes_issue_payload() -> None:
    service = IssueService(provider=FakeIssueProvider())

    result = service.get("DEMO-1")

    assert result["key"] == "DEMO-1"
    assert result["status"] == {"name": "Open"}
    assert result["assignee"] == {"display_name": "Example Author", "name": "Example Author"}
    assert result["reporter"] == {"display_name": "reviewer-one", "name": "reviewer-one"}


def test_issue_service_exposes_raw_issue_payload() -> None:
    provider = FakeIssueProvider()
    service = IssueService(provider=provider)

    result = service.get_raw("DEMO-1")

    assert result["fields"]["summary"] == "Example issue summary"
    assert result["fields"]["status"]["name"] == "Open"


def test_issue_service_search_normalizes_without_refetching_each_issue() -> None:
    provider = FakeIssueProvider()
    service = IssueService(provider=provider)

    result = service.search("project = DEMO", start=0, limit=2)

    assert result["total"] == 2
    assert result["start_at"] == 0
    assert result["max_results"] == 2
    assert [item["key"] for item in result["issues"]] == ["DEMO-1", "DEMO-2"]
    assert [item["status"]["name"] for item in result["issues"]] == ["Open", "In Progress"]
    assert provider.get_issue_calls == 0


def test_issue_service_search_page_returns_collection_page() -> None:
    service = IssueService(provider=FakeIssueProvider())

    page = service.search_page("project = DEMO", start=0, limit=2)

    assert isinstance(page, CollectionPage)
    assert page.start == 0
    assert page.limit == 2
    assert page.total == 2
    assert [item["key"] for item in page.items] == ["DEMO-1", "DEMO-2"]


def test_issue_service_delete_returns_success_payload() -> None:
    class FakeDeleteProvider:
        def delete_issue(self, issue_key: str) -> None:
            assert issue_key == "DEMO-1"

    service = IssueService(provider=FakeDeleteProvider())

    assert service.delete("DEMO-1") == {"key": "DEMO-1", "deleted": True}


def test_issue_service_batch_create_normalizes_created_issues() -> None:
    class FakeBatchProvider:
        def create_issues(self, issues: list[dict]) -> list[dict]:
            assert issues == [
                {
                    "project": {"key": "DEMO"},
                    "issuetype": {"name": "Task"},
                    "summary": "First issue",
                }
            ]
            return [{"key": "DEMO-1"}]

    service = IssueService(provider=FakeBatchProvider())

    result = service.batch_create(
        [
            {
                "project": {"key": "DEMO"},
                "issuetype": {"name": "Task"},
                "summary": "First issue",
            }
        ]
    )

    assert result == {"issues": [{"key": "DEMO-1"}]}


def test_issue_service_batch_create_preserves_unexpected_payload_shapes() -> None:
    class FakeBatchProvider:
        def create_issues(self, issues: list[dict]) -> list[object]:
            assert issues == [{"summary": "First issue"}]
            return [{"error": "validation failed"}, "unexpected"]

    service = IssueService(provider=FakeBatchProvider())

    result = service.batch_create([{"summary": "First issue"}])

    assert result == {"issues": [{"error": "validation failed"}, "unexpected"]}
