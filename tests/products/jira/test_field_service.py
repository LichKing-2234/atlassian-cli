from atlassian_cli.products.jira.services.field import FieldService


class FakeFieldProvider:
    def search_fields(self, keyword: str, *, limit: int) -> list[dict]:
        assert keyword == "story"
        assert limit == 1
        return [
            {
                "id": "customfield_10001",
                "name": "Story Points",
                "schema": {"type": "number"},
            }
        ]

    def get_field_options(
        self,
        field_id: str,
        project_key: str,
        issue_type: str,
        *,
        contains: str | None,
        return_limit: int,
    ) -> list[dict]:
        assert field_id == "customfield_10001"
        assert project_key == "DEMO"
        assert issue_type == "Bug"
        assert contains == "one"
        assert return_limit == 1
        return [{"id": "1", "value": "1"}, {"id": "2", "value": "2"}]


def test_field_service_search_normalizes_results() -> None:
    service = FieldService(provider=FakeFieldProvider())

    result = service.search("story", limit=1)

    assert result == {
        "results": [
            {"id": "customfield_10001", "name": "Story Points", "type": "number"},
        ]
    }


def test_field_service_options_normalizes_results() -> None:
    service = FieldService(provider=FakeFieldProvider())

    result = service.options(
        "customfield_10001",
        project_key="DEMO",
        issue_type="Bug",
        contains="one",
        return_limit=1,
    )

    assert result["results"] == [{"id": "1", "value": "1"}, {"id": "2", "value": "2"}]
