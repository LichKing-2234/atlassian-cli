from typing import Protocol


class ConfluenceProvider(Protocol):
    def get_page(self, page_id: str) -> dict: ...
