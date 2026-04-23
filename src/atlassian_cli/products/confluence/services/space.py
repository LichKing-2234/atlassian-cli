from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceSpace


class SpaceService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> dict:
        raw = self.provider.list_spaces(start=start, limit=limit)
        spaces = [
            ConfluenceSpace.from_api_response(item).to_simplified_dict()
            for item in raw.get("results", [])
            if isinstance(item, dict)
        ]
        payload = {"results": spaces}
        if raw.get("start") is not None:
            payload["start_at"] = raw["start"]
        if raw.get("limit") is not None:
            payload["max_results"] = raw["limit"]
        return payload

    def get(self, space_key: str) -> dict:
        return ConfluenceSpace.from_api_response(
            self.provider.get_space(space_key)
        ).to_simplified_dict()

    def list_raw(self, start: int, limit: int) -> dict:
        return self.provider.list_spaces(start=start, limit=limit)

    def get_raw(self, space_key: str) -> dict:
        return self.provider.get_space(space_key)
