from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequest


def test_bitbucket_pr_schema_handles_missing_author_and_reviewers() -> None:
    pr = BitbucketPullRequest.from_api_response(
        {
            "id": 42,
            "title": "Example pull request",
            "state": "OPEN",
            "fromRef": {"displayId": "feature/DEMO-1234/example-change"},
            "toRef": {"displayId": "main"},
        }
    )

    simplified = pr.to_simplified_dict()

    assert simplified["from_ref"]["display_id"] == "feature/DEMO-1234/example-change"
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
            "author": {"user": {"displayName": "Example Author", "name": "example-user@example.com"}},
            "reviewers": [{"user": {"displayName": "reviewer-one", "name": "reviewer-one@example.com"}}],
            "participants": [{"user": {"displayName": "Code Owners"}}],
            "links": {"self": [{"href": "https://bitbucket.example.com/pr/42"}]},
            "fromRef": {
                "displayId": "feature/DEMO-1234/example-change",
                "id": "refs/heads/feature/DEMO-1234/example-change",
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
        "author": {"display_name": "Example Author", "name": "example-user@example.com"},
        "reviewers": [{"approved": False, "display_name": "reviewer-one", "name": "reviewer-one@example.com"}],
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2024-01-02 00:00:00",
    }
