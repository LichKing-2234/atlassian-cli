from atlassian_cli.products.bitbucket.services.pr import PullRequestService


class FakePullRequestProvider:
    def list_pull_requests(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return [
            {
                "id": 42,
                "title": "Ship output cleanup",
                "state": "OPEN",
                "author": {"user": {"displayName": "Alice"}},
                "reviewers": [{"user": {"displayName": "Bob"}, "approved": True}],
                "fromRef": {"displayId": "feature/output"},
                "toRef": {"displayId": "main"},
            }
        ]

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.list_pull_requests(project_key, repo_slug, "OPEN")[0]


def test_pull_request_service_normalizes_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get("AI", "agora-skills", 42)

    assert result == {
        "id": 42,
        "title": "Ship output cleanup",
        "state": "OPEN",
        "author": {"display_name": "Alice"},
        "from_ref": {"display_id": "feature/output"},
        "to_ref": {"display_id": "main"},
        "reviewers": [{"display_name": "Bob", "approved": True}],
    }


def test_pull_request_service_exposes_raw_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get_raw("AI", "agora-skills", 42)

    assert "author" in result
    assert "user" in result["author"]
