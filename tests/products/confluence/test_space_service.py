from atlassian_cli.products.confluence.services.space import SpaceService


class FakeSpaceProvider:
    def list_spaces(self, start: int, limit: int) -> dict:
        return {
            "results": [
                {
                    "id": 1,
                    "key": "PROJ",
                    "name": "Demo Project",
                    "type": "global",
                    "status": "current",
                }
            ],
            "start": start,
            "limit": limit,
        }

    def get_space(self, space_key: str) -> dict:
        return self.list_spaces(start=0, limit=25)["results"][0]


def test_space_service_normalizes_space_payload() -> None:
    service = SpaceService(provider=FakeSpaceProvider())

    result = service.list(start=0, limit=25)

    assert result == {
        "results": [
            {
                "id": "1",
                "key": "PROJ",
                "name": "Demo Project",
                "type": "global",
                "status": "current",
            }
        ],
        "start_at": 0,
        "max_results": 25,
    }


def test_space_service_exposes_raw_space_payload() -> None:
    service = SpaceService(provider=FakeSpaceProvider())

    result = service.get_raw("PROJ")

    assert result["status"] == "current"
    assert result["type"] == "global"
