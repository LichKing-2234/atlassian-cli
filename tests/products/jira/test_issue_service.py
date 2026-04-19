from atlassian_cli.products.jira.services.issue import IssueService


class FakeIssueProvider:
    def get_issue(self, issue_key: str) -> dict:
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


def test_issue_service_normalizes_issue_payload() -> None:
    service = IssueService(provider=FakeIssueProvider())

    result = service.get("OPS-1")

    assert result["key"] == "OPS-1"
    assert result["status"] == "Open"
    assert result["assignee"] == "Alice"
