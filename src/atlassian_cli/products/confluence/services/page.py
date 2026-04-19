from atlassian_cli.products.confluence.schemas import ConfluencePage


class PageService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, page_id: str) -> dict:
        raw = self.provider.get_page(page_id)
        page = ConfluencePage(
            id=raw["id"],
            title=raw["title"],
            space_key=raw["space"]["key"],
            version=(raw.get("version") or {}).get("number"),
        )
        return page.model_dump()

    def create(self, *, space_key: str, title: str, body: str) -> dict:
        return self.provider.create_page(space_key=space_key, title=title, body=body)

    def update(self, page_id: str, *, title: str, body: str) -> dict:
        return self.provider.update_page(page_id=page_id, title=title, body=body)

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
