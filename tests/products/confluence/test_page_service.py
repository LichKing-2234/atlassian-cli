from atlassian_cli.products.confluence.services.page import PageService


class FakePageProvider:
    def get_page(self, page_id: str) -> dict:
        return {
            "id": page_id,
            "title": "Runbook",
            "type": "page",
            "space": {"key": "OPS", "name": "Operations"},
            "version": {"number": 7},
            "body": {"view": {"value": "<p>huge html</p>"}},
        }


def test_page_service_normalizes_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get("1234")

    assert result == {
        "id": "1234",
        "title": "Runbook",
        "type": "page",
        "space": {"key": "OPS", "name": "Operations"},
        "version": 7,
    }


def test_page_service_exposes_raw_page_payload() -> None:
    service = PageService(provider=FakePageProvider())

    result = service.get_raw("1234")

    assert "body" in result
