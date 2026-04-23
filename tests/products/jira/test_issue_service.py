from atlassian_cli.products.jira.services.issue import IssueService


class FakeIssueProvider:
    def __init__(self) -> None:
        self.get_issue_calls = 0

    def get_issue(self, issue_key: str) -> dict:
        self.get_issue_calls += 1
        return {
            "key": issue_key,
            "fields": {
                "summary": "Broken deploy",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
                "priority": {"name": "High"},
                "updated": "2026-04-19T09:00:00.000+0000",
            },
        }

    def search_issues(self, jql: str, start: int, limit: int) -> dict:
        assert jql == "project = OPS"
        assert start == 0
        assert limit == 2
        return {
            "total": 2,
            "startAt": start,
            "maxResults": limit,
            "issues": [
                {
                    "key": "OPS-1",
                    "fields": {
                        "summary": "Broken deploy",
                        "status": {"name": "Open"},
                        "assignee": {"displayName": "Alice"},
                        "reporter": {"displayName": "Bob"},
                        "priority": {"name": "High"},
                        "updated": "2026-04-19T09:00:00.000+0000",
                    },
                },
                {
                    "key": "OPS-2",
                    "fields": {
                        "summary": "Fix flaky test",
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "Carol"},
                        "reporter": {"displayName": "Bob"},
                        "priority": {"name": "Medium"},
                        "updated": "2026-04-20T09:00:00.000+0000",
                    },
                },
            ],
        }


def test_issue_service_normalizes_issue_payload() -> None:
    service = IssueService(provider=FakeIssueProvider())

    result = service.get("OPS-1")

    assert result["key"] == "OPS-1"
    assert result["status"] == {"name": "Open"}
    assert result["assignee"] == {"display_name": "Alice", "name": "Alice"}
    assert result["reporter"] == {"display_name": "Bob", "name": "Bob"}


def test_issue_service_exposes_raw_issue_payload() -> None:
    provider = FakeIssueProvider()
    service = IssueService(provider=provider)

    result = service.get_raw("OPS-1")

    assert result["fields"]["summary"] == "Broken deploy"
    assert result["fields"]["status"]["name"] == "Open"


def test_issue_service_search_normalizes_without_refetching_each_issue() -> None:
    provider = FakeIssueProvider()
    service = IssueService(provider=provider)

    result = service.search("project = OPS", start=0, limit=2)

    assert result["total"] == 2
    assert result["start_at"] == 0
    assert result["max_results"] == 2
    assert [item["key"] for item in result["issues"]] == ["OPS-1", "OPS-2"]
    assert [item["status"]["name"] for item in result["issues"]] == ["Open", "In Progress"]
    assert provider.get_issue_calls == 0
