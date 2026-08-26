from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceLabel


class LabelService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    @staticmethod
    def _normalize(raw: dict) -> dict:
        return {
            "results": [
                ConfluenceLabel.from_api_response(item).to_simplified_dict()
                for item in raw.get("results", [])
                if isinstance(item, dict)
            ]
        }

    def list(self, page_id: str) -> dict:
        return self._normalize(self.provider.get_page_labels(page_id))

    def list_raw(self, page_id: str) -> dict:
        return self.provider.get_page_labels(page_id)

    def add(self, page_id: str, name: str) -> dict:
        return self._normalize(self.provider.add_page_label(page_id, name))

    def add_raw(self, page_id: str, name: str) -> dict:
        return self.provider.add_page_label(page_id, name)
