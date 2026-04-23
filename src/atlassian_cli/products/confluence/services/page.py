from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluencePage


class PageService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def _page_kwargs(self) -> dict:
        client = getattr(self.provider, "client", None)
        return {"base_url": getattr(client, "url", None), "is_cloud": False}

    def get(self, page_id: str) -> dict:
        return ConfluencePage.from_api_response(
            self.provider.get_page(page_id), **self._page_kwargs()
        ).to_simplified_dict()

    def get_raw(self, page_id: str) -> dict:
        return self.provider.get_page(page_id)

    def create(self, *, space_key: str, title: str, body: str) -> dict:
        raw = self.provider.create_page(space_key=space_key, title=title, body=body)
        return ConfluencePage.from_api_response(raw, **self._page_kwargs()).to_simplified_dict()

    def create_raw(self, *, space_key: str, title: str, body: str) -> dict:
        return self.provider.create_page(space_key=space_key, title=title, body=body)

    def update(self, page_id: str, *, title: str, body: str) -> dict:
        raw = self.provider.update_page(page_id=page_id, title=title, body=body)
        return ConfluencePage.from_api_response(raw, **self._page_kwargs()).to_simplified_dict()

    def update_raw(self, page_id: str, *, title: str, body: str) -> dict:
        return self.provider.update_page(page_id=page_id, title=title, body=body)

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)

    def delete_raw(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
