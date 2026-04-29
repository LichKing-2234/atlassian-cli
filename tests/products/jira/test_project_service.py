from atlassian_cli.products.jira.services.project import ProjectService


class FakeProjectProvider:
    def list_projects(self) -> list[dict]:
        return [
            {
                "key": "DEMO",
                "name": "Demo Project",
                "avatarUrls": {"48x48": "https://example.com/avatar.png"},
                "projectTypeKey": "software",
            }
        ]

    def get_project(self, project_key: str) -> dict:
        return self.list_projects()[0]


def test_project_service_normalizes_project_payload() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.get("DEMO")

    assert result == {
        "key": "DEMO",
        "name": "Demo Project",
        "avatar_url": "https://example.com/avatar.png",
    }


def test_project_service_exposes_raw_project_payload() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.get_raw("DEMO")

    assert "avatarUrls" in result


def test_project_service_list_returns_results_envelope() -> None:
    service = ProjectService(provider=FakeProjectProvider())

    result = service.list()

    assert result == {
        "results": [
            {
                "key": "DEMO",
                "name": "Demo Project",
                "avatar_url": "https://example.com/avatar.png",
            }
        ]
    }
