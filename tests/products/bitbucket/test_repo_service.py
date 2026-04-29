from atlassian_cli.products.bitbucket.services.repo import RepoService


class FakeRepoProvider:
    def list_repos(self, project_key: str | None, start: int, limit: int) -> list[dict]:
        return [
            {
                "project": {"key": project_key or "PROJ", "name": "Demo Project"},
                "slug": "infra",
                "name": "Infra",
                "state": "AVAILABLE",
            }
        ]

    def get_repo(self, project_key: str, repo_slug: str) -> dict:
        return {
            "project": {"key": project_key, "name": "Demo Project"},
            "slug": repo_slug,
            "name": "infra",
            "state": "AVAILABLE",
            "links": {"clone": []},
        }


def test_repo_service_normalizes_repo_payload() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.get("PROJ", "infra")

    assert result == {
        "project": {"key": "PROJ", "name": "Demo Project"},
        "slug": "infra",
        "name": "infra",
        "state": "AVAILABLE",
        "links": {"clone": []},
    }


def test_repo_service_exposes_raw_repo_payload() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.get_raw("PROJ", "infra")

    assert "links" in result


def test_repo_service_list_returns_results_envelope() -> None:
    service = RepoService(provider=FakeRepoProvider())

    result = service.list("PROJ", start=0, limit=25)

    assert result == {
        "results": [
            {
                "slug": "infra",
                "name": "Infra",
                "state": "AVAILABLE",
                "project": {"key": "PROJ", "name": "Demo Project"},
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }


def test_repo_service_create_normalizes_repo_payload() -> None:
    class CreateRepoProvider(FakeRepoProvider):
        def create_repo(self, project_key: str, name: str, scm_id: str) -> dict:
            assert project_key == "~example_user"
            assert name == "atlassian-cli-e2e-temp"
            assert scm_id == "git"
            return {
                "slug": "atlassian-cli-e2e-temp",
                "name": "atlassian-cli-e2e-temp",
                "state": "AVAILABLE",
                "project": {"key": "~example_user", "name": "example_user"},
            }

    service = RepoService(provider=CreateRepoProvider())

    result = service.create("~example_user", "atlassian-cli-e2e-temp", "git")

    assert result == {
        "slug": "atlassian-cli-e2e-temp",
        "name": "atlassian-cli-e2e-temp",
        "state": "AVAILABLE",
        "project": {"key": "~example_user", "name": "example_user"},
    }
