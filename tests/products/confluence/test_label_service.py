from atlassian_cli.products.confluence.services.label import LabelService


class FakeLabelProvider:
    def get_page_labels(self, page_id: str) -> dict:
        assert page_id == "1234"
        return {
            "results": [
                {
                    "id": "55",
                    "name": "example-repo",
                    "prefix": "global",
                    "label": "example-repo",
                    "type": "label",
                }
            ]
        }

    def add_page_label(self, page_id: str, name: str) -> dict:
        assert page_id == "1234"
        assert name == "example-repo"
        return self.get_page_labels(page_id)


def test_label_service_list_normalizes_results() -> None:
    service = LabelService(provider=FakeLabelProvider())

    assert service.list("1234") == {
        "results": [
            {
                "id": "55",
                "name": "example-repo",
                "prefix": "global",
                "label": "example-repo",
            }
        ]
    }


def test_label_service_add_normalizes_read_back_results() -> None:
    service = LabelService(provider=FakeLabelProvider())

    result = service.add("1234", "example-repo")

    assert result["results"][0]["name"] == "example-repo"
