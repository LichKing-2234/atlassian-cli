from atlassian_cli.products.confluence.services.page import PageService


class FakePageProvider:
    def get_page(self, page_id: str) -> dict:
        return {
            "id": page_id,
            "title": "Runbook",
            "space": {"key": "OPS"},
            "version": {"number": 7},
        }


def test_page_service_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get("1234")

    assert result["id"] == "1234"
    assert result["title"] == "Runbook"
    assert result["space_key"] == "OPS"
