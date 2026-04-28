from atlassian_cli.products.jira.services.field import FieldService


class FakeFieldProvider:
    def search_fields(self, query: str) -> list[dict]:
        assert query == "story"
        return [
            {
                "id": "customfield_10001",
                "name": "Story Points",
                "schema": {"type": "number"},
            }
        ]

    def get_field_options(self, field_id: str, project_key: str, issue_type: str) -> list[dict]:
        assert field_id == "customfield_10001"
        assert project_key == "OPS"
        assert issue_type == "Bug"
        return [{"id": "1", "value": "1"}, {"id": "2", "value": "2"}]


def test_field_service_search_normalizes_results() -> None:
    service = FieldService(provider=FakeFieldProvider())

    result = service.search("story")

    assert result == {
        "results": [
            {"id": "customfield_10001", "name": "Story Points", "type": "number"},
        ]
    }


def test_field_service_options_normalizes_results() -> None:
    service = FieldService(provider=FakeFieldProvider())

    result = service.options("customfield_10001", project_key="OPS", issue_type="Bug")

    assert result["results"] == [{"id": "1", "value": "1"}, {"id": "2", "value": "2"}]
