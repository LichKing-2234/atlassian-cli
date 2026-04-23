from atlassian_cli.products.jira.schemas import JiraIssue, JiraSearchResult, JiraUser


def test_jira_issue_from_api_response_builds_rich_resource() -> None:
    issue = JiraIssue.from_api_response(
        {
            "id": 10001,
            "key": "OPS-1",
            "self": "https://jira.example.com/rest/api/2/issue/10001",
            "fields": {
                "summary": "Broken deploy",
                "description": "Investigate release failure",
                "status": {"name": "Open"},
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alice", "name": "alice"},
                "reporter": {"displayName": "Bob", "name": "bob"},
                "labels": ["release"],
                "project": {"key": "OPS", "name": "Operations"},
                "created": "2026-04-23T09:00:00.000+0000",
                "updated": "2026-04-23T10:00:00.000+0000",
            },
        }
    )

    assert issue.id == "10001"
    assert issue.issue_type.name == "Bug"

    simplified = issue.to_simplified_dict()
    assert simplified["project"]["key"] == "OPS"
    assert simplified["url"] == "https://jira.example.com/rest/api/2/issue/10001"


def test_jira_user_from_api_response_handles_cloud_shape() -> None:
    user = JiraUser.from_api_response(
        {
            "accountId": "abc-123",
            "displayName": "Cloud User",
            "emailAddress": "cloud@example.com",
            "avatarUrls": {"48x48": "https://example.com/avatar.png"},
        }
    )

    simplified = user.to_simplified_dict()

    assert simplified["account_id"] == "abc-123"
    assert simplified["display_name"] == "Cloud User"
    assert simplified["name"] == "Cloud User"


def test_jira_search_result_from_api_response_preserves_metadata() -> None:
    result = JiraSearchResult.from_api_response(
        {
            "total": 2,
            "startAt": 5,
            "maxResults": 2,
            "issues": [
                {"id": 1, "key": "OPS-1", "fields": {"summary": "One", "status": {"name": "Open"}}},
                {"id": 2, "key": "OPS-2", "fields": {"summary": "Two", "status": {"name": "Done"}}},
            ],
        }
    )

    simplified = result.to_simplified_dict()

    assert simplified["total"] == 2
    assert simplified["start_at"] == 5
    assert [issue["key"] for issue in simplified["issues"]] == ["OPS-1", "OPS-2"]
