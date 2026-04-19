class SpaceService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, start: int, limit: int) -> list[dict]:
        return self.provider.list_spaces(start=start, limit=limit)

    def get(self, space_key: str) -> dict:
        return self.provider.get_space(space_key)
