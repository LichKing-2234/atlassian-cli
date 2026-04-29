from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequest


def test_bitbucket_pr_schema_handles_missing_author_and_reviewers() -> None:
    pr = BitbucketPullRequest.from_api_response(
        {
            "id": 42,
            "title": "Example pull request",
            "state": "OPEN",
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
        }
    )

    simplified = pr.to_simplified_dict()

    assert simplified["from_ref"]["display_id"] == "feature/output"
    assert "author" not in simplified


def test_bitbucket_pr_schema_exposes_summary_oriented_list_payload() -> None:
    pr = BitbucketPullRequest.from_api_response(
        {
            "id": 42,
            "title": "Example pull request",
            "description": "Long body that should stay out of list output",
            "state": "OPEN",
            "open": True,
            "closed": False,
            "createdDate": 1704067200000,
            "updatedDate": 1704153600000,
            "author": {"user": {"displayName": "Alice", "name": "alice@example.com"}},
            "reviewers": [{"user": {"displayName": "Bob", "name": "bob@example.com"}}],
            "participants": [{"user": {"displayName": "Code Owners"}}],
            "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
            "fromRef": {
                "displayId": "feature/output",
                "id": "refs/heads/feature/output",
                "latestCommit": "abc123",
            },
            "toRef": {
                "displayId": "main",
                "id": "refs/heads/main",
                "latestCommit": "def456",
            },
        }
    )

    summarized = pr.to_list_dict()

    assert summarized == {
        "id": 42,
        "title": "Example pull request",
        "state": "OPEN",
        "author": {"display_name": "Alice", "name": "alice@example.com"},
        "reviewers": [{"approved": False, "display_name": "Bob", "name": "bob@example.com"}],
        "from_ref": {"display_id": "feature/output"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2024-01-02 00:00:00",
    }
