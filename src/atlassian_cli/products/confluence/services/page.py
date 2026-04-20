from atlassian_cli.products.confluence.schemas import ConfluencePage, ConfluenceSpaceRef


class PageService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def _normalize_page(self, raw: dict) -> dict:
        page = ConfluencePage(
            id=raw["id"],
            title=raw["title"],
            type=raw.get("type"),
            space=ConfluenceSpaceRef(
                key=raw["space"]["key"],
                name=raw["space"].get("name"),
            ),
            version=(raw.get("version") or {}).get("number"),
        )
        return page.model_dump(exclude_none=True)

    def get(self, page_id: str) -> dict:
        return self._normalize_page(self.provider.get_page(page_id))

    def get_raw(self, page_id: str) -> dict:
        return self.provider.get_page(page_id)

    def create(self, *, space_key: str, title: str, body: str) -> dict:
        return self._normalize_page(
            self.provider.create_page(space_key=space_key, title=title, body=body)
        )

    def create_raw(self, *, space_key: str, title: str, body: str) -> dict:
        return self.provider.create_page(space_key=space_key, title=title, body=body)

    def update(self, page_id: str, *, title: str, body: str) -> dict:
        return self._normalize_page(
            self.provider.update_page(page_id=page_id, title=title, body=body)
        )

    def update_raw(self, page_id: str, *, title: str, body: str) -> dict:
        return self.provider.update_page(page_id=page_id, title=title, body=body)

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)

    def delete_raw(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
