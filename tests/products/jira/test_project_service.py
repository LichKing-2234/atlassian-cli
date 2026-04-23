from atlassian_cli.products.jira.services.project import ProjectService


class FakeProjectProvider:
    def list_projects(self) -> list[dict]:
        return [
            {
                "key": "OPS",
                "name": "Operations",
                "avatarUrls": {"48x48": "https://example.com/avatar.png"},
                "projectTypeKey": "software",
            }
        ]

    def get_project(self, project_key: str) -> dict:
        return self.list_projects()[0]


def test_project_service_normalizes_project_payload() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.get("OPS")

    assert result == {
        "key": "OPS",
        "name": "Operations",
        "avatar_url": "https://example.com/avatar.png",
    }


def test_project_service_exposes_raw_project_payload() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.get_raw("OPS")

    assert "avatarUrls" in result


def test_project_service_list_returns_results_envelope() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.list()

    assert result == {
        "results": [
            {
                "key": "OPS",
                "name": "Operations",
                "avatar_url": "https://example.com/avatar.png",
            }
        ]
    }
