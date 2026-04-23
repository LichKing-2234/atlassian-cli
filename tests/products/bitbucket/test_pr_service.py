from atlassian_cli.products.bitbucket.services.pr import PullRequestService


class FakePullRequestProvider:
    def __init__(self) -> None:
        self.merge_calls = []

    def list_pull_requests(self, project_key: str, repo_slug: str, state: str) -> list[dict]:
        return [
            {
                "id": 42,
                "title": "Ship output cleanup",
                "state": "OPEN",
                "version": 7,
                "reviewers": [{"user": {"displayName": "Bob"}, "approved": True}],
                "fromRef": {"displayId": "feature/output"},
                "toRef": {"displayId": "main"},
            }
        ]

    def get_pull_request(self, project_key: str, repo_slug: str, pr_id: int) -> dict:
        return self.list_pull_requests(project_key, repo_slug, "OPEN")[0]

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
            "title": "Ship output cleanup",
            "state": "MERGED",
            "fromRef": {"displayId": "feature/output"},
            "toRef": {"displayId": "main"},
        }


def test_pull_request_service_normalizes_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get("AI", "agora-skills", 42)

    assert result == {
        "id": 42,
        "title": "Ship output cleanup",
        "state": "OPEN",
        "from_ref": {"display_id": "feature/output"},
        "to_ref": {"display_id": "main"},
        "reviewers": [{"display_name": "Bob", "approved": True}],
    }


def test_pull_request_service_exposes_raw_payload() -> None:
    service = PullRequestService(provider=FakePullRequestProvider())

    result = service.get_raw("AI", "agora-skills", 42)

    assert "version" in result


def test_pull_request_service_merge_prefetches_title_and_version() -> None:
    provider = FakePullRequestProvider()
    service = PullRequestService(provider=provider)

    result = service.merge("OPS", "infra", 42)

    assert result["state"] == "MERGED"
    assert provider.merge_calls == [
        ("OPS", "infra", 42, "Merge pull request #42: Ship output cleanup", 7)
    ]
