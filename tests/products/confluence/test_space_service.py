from atlassian_cli.products.confluence.services.space import SpaceService


class FakeSpaceProvider:
    def list_spaces(self, start: int, limit: int) -> list[dict]:
        return [
            {
                "key": "OPS",
                "name": "Operations",
                "_expandable": {"homepage": "/rest/api/content/123"},
                "_links": {"webui": "/display/OPS"},
            }
        ]

    def get_space(self, space_key: str) -> dict:
        return self.list_spaces(start=0, limit=25)[0]


def test_space_service_normalizes_space_payload() -> None:
    service = SpaceService(provider=FakeSpaceProvider())

    result = service.list(start=0, limit=25)

    assert result == [{"key": "OPS", "name": "Operations"}]


def test_space_service_exposes_raw_space_payload() -> None:
    service = SpaceService(provider=FakeSpaceProvider())

    result = service.get_raw("OPS")

    assert "_expandable" in result
