from atlassian_cli.products.bitbucket.schemas import (
    BitbucketBuildStatus,
    BitbucketPullRequest,
    BitbucketPullRequestBuildStatusSummary,
    BitbucketPullRequestComment,
)


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
            "author": {"user": {"displayName": "Example Author", "name": "example-user-id"}},
            "reviewers": [{"user": {"displayName": "reviewer-one", "name": "reviewer-one-id"}}],
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
        "author": {"display_name": "Example Author", "name": "example-user-id"},
        "reviewers": [
            {"approved": False, "display_name": "reviewer-one", "name": "reviewer-one-id"}
        ],
        "from_ref": {"display_id": "feature/DEMO-1234/example-change"},
        "to_ref": {"display_id": "main"},
        "updated_date": "2024-01-02 00:00:00",
    }


def test_bitbucket_pr_comment_schema_normalizes_parent_and_anchor() -> None:
    comment = BitbucketPullRequestComment.from_api_response(
        {
            "id": 1001,
            "version": 3,
            "text": "example comment",
            "author": {"displayName": "Example Author", "name": "example-user-id"},
            "createdDate": 1704153600000,
            "updatedDate": 1704153600000,
            "parent": {"id": 1000},
            "anchor": {"path": "src/example.py", "line": 12, "lineType": "ADDED"},
        }
    )

    assert comment.to_simplified_dict() == {
        "id": "1001",
        "version": 3,
        "text": "example comment",
        "author": {"display_name": "Example Author", "name": "example-user-id"},
        "created_date": "1704153600000",
        "updated_date": "1704153600000",
        "parent": {"id": "1000"},
        "anchor": {"path": "src/example.py", "line": 12, "line_type": "ADDED"},
    }


def test_bitbucket_build_status_schema_normalizes_common_fields() -> None:
    status = BitbucketBuildStatus.from_api_response(
        {
            "key": "DEMO",
            "name": "Example build",
            "state": "SUCCESSFUL",
            "url": "https://bitbucket.example.com/build/DEMO",
            "description": "example response",
            "dateAdded": 1704153600000,
        }
    )

    assert status.to_simplified_dict() == {
        "key": "DEMO",
        "name": "Example build",
        "state": "SUCCESSFUL",
        "url": "https://bitbucket.example.com/build/DEMO",
        "description": "example response",
        "date_added": "1704153600000",
    }


def test_bitbucket_pr_build_status_summary_preserves_empty_commits() -> None:
    summary = BitbucketPullRequestBuildStatusSummary(
        pull_request={"id": 42, "project_key": "DEMO", "repo_slug": "example-repo"},
        overall_state="UNKNOWN",
        commits=[],
    )

    assert summary.to_simplified_dict() == {
        "pull_request": {"id": 42, "project_key": "DEMO", "repo_slug": "example-repo"},
        "overall_state": "UNKNOWN",
        "commits": [],
    }
