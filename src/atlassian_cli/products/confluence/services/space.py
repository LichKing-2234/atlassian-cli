from atlassian_cli.products.confluence.schemas import ConfluenceSpace


class SpaceService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> "list[dict]":
        return [
            self._normalize_space(item)
            for item in self.provider.list_spaces(start=start, limit=limit)
        ]

    def get(self, space_key: str) -> dict:
        return self._normalize_space(self.provider.get_space(space_key))

    def list_raw(self, start: int, limit: int) -> "list[dict]":
        return self.provider.list_spaces(start=start, limit=limit)

    def get_raw(self, space_key: str) -> dict:
        return self.provider.get_space(space_key)

    def _normalize_space(self, raw: dict) -> dict:
        space = ConfluenceSpace(
            key=raw["key"],
            name=raw["name"],
        )
        return space.model_dump(exclude_none=True)
