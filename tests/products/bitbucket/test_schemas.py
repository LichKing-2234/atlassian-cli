from atlassian_cli.products.bitbucket.schemas import BitbucketPullRequest


def test_bitbucket_pr_schema_handles_missing_author_and_reviewers() -> None:
    pr = BitbucketPullRequest.from_api_response(
        {
            "id": 42,
            "title": "Ship output cleanup",
            "state": "OPEN",
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
        }
    )

    simplified = pr.to_simplified_dict()

    assert simplified["from_ref"]["display_id"] == "feature/output"
    assert "author" not in simplified
