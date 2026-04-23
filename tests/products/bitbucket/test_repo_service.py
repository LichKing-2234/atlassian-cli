from atlassian_cli.products.bitbucket.services.repo import RepoService


class FakeRepoProvider:
    def list_repos(self, project_key: str | None, start: int, limit: int) -> list[dict]:
        return [
            {
                "project": {"key": project_key or "OPS", "name": "Operations"},
                "slug": "infra",
                "name": "Infra",
                "state": "AVAILABLE",
            }
        ]

    def get_repo(self, project_key: str, repo_slug: str) -> dict:
        return {
            "project": {"key": project_key, "name": "Operations"},
            "slug": repo_slug,
            "name": "infra",
            "state": "AVAILABLE",
            "links": {"clone": []},
        }


def test_repo_service_normalizes_repo_payload() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.get("OPS", "infra")

    assert result == {
        "project": {"key": "OPS", "name": "Operations"},
        "slug": "infra",
        "name": "infra",
        "state": "AVAILABLE",
        "links": {"clone": []},
    }


def test_repo_service_exposes_raw_repo_payload() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.get_raw("OPS", "infra")

    assert "links" in result


def test_repo_service_list_returns_results_envelope() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.list("OPS", start=0, limit=25)

    assert result == {
        "results": [
            {
                "slug": "infra",
                "name": "Infra",
                "state": "AVAILABLE",
                "project": {"key": "OPS", "name": "Operations"},
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }
