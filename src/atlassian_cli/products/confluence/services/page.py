from difflib import unified_diff

from atlassian_cli.models.common import nested_get
from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluencePage


class PageService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def _page_kwargs(self) -> dict:
        client = getattr(self.provider, "client", None)
        return {"base_url": getattr(client, "url", None), "is_cloud": False}

    def _normalize_page(self, payload: dict) -> dict:
        return ConfluencePage.from_api_response(payload, **self._page_kwargs()).to_simplified_dict()

    def get(self, page_id: str) -> dict:
        return self._normalize_page(self.provider.get_page(page_id))

    def get_raw(self, page_id: str) -> dict:
        return self.provider.get_page(page_id)

    def get_by_title(self, space_key: str, title: str) -> dict:
        page = self.provider.get_page_by_title(space_key, title)
        if page is None:
            return {}
        return self._normalize_page(page)

    def get_by_title_raw(self, space_key: str, title: str) -> dict | None:
        return self.provider.get_page_by_title(space_key, title)

    def search(self, query: str, *, limit: int) -> dict:
        return {
            "results": [self._normalize_page(item) for item in self.provider.search_pages(query, limit)]
        }

    def search_raw(self, query: str, *, limit: int) -> list[dict]:
        return self.provider.search_pages(query, limit)

    def children(self, page_id: str) -> dict:
        return {
            "results": [self._normalize_page(item) for item in self.provider.get_page_children(page_id)]
        }

    def children_raw(self, page_id: str) -> list[dict]:
        return self.provider.get_page_children(page_id)

    def tree(self, space_key: str) -> dict:
        root = self.provider.get_space_homepage(space_key)
        results: list[dict] = []
        queue: list[tuple[dict, int]] = [(root, 0)]

        while queue:
            page, depth = queue.pop(0)
            normalized = self._normalize_page(page)
            normalized["depth"] = depth
            results.append(normalized)
            for child in self.provider.get_page_children(str(page.get("id", ""))):
                queue.append((child, depth + 1))

        return {"results": results}

    def tree_raw(self, space_key: str) -> dict:
        return self.tree(space_key)

    def history(self, page_id: str, *, version: int) -> dict:
        return self._normalize_page(self.provider.get_page_version(page_id, version))

    def history_raw(self, page_id: str, *, version: int) -> dict:
        return self.provider.get_page_version(page_id, version)

    def diff(self, page_id: str, *, from_version: int, to_version: int) -> dict:
        from_page = self.provider.get_page_version(page_id, from_version)
        to_page = self.provider.get_page_version(page_id, to_version)
        from_text = nested_get(from_page, "body", "storage", "value") or ""
        to_text = nested_get(to_page, "body", "storage", "value") or ""
        diff_text = "\n".join(
            unified_diff(
                str(from_text).splitlines(),
                str(to_text).splitlines(),
                fromfile=f"version-{from_version}",
                tofile=f"version-{to_version}",
                lineterm="",
            )
        )
        return {
            "page_id": page_id,
            "from_version": from_version,
            "to_version": to_version,
            "diff": diff_text,
        }

    def diff_raw(self, page_id: str, *, from_version: int, to_version: int) -> dict:
        return self.diff(page_id, from_version=from_version, to_version=to_version)

    def move(
        self,
        page_id: str,
        *,
        target_parent_id: str | None = None,
        target_space_key: str | None = None,
        position: str = "append",
    ) -> dict:
        return self._normalize_page(
            self.provider.move_page(
                page_id,
                target_parent_id=target_parent_id,
                target_space_key=target_space_key,
                position=position,
            )
        )

    def move_raw(
        self,
        page_id: str,
        *,
        target_parent_id: str | None = None,
        target_space_key: str | None = None,
        position: str = "append",
    ) -> dict:
        return self.provider.move_page(
            page_id,
            target_parent_id=target_parent_id,
            target_space_key=target_space_key,
            position=position,
        )

    def create(self, *, space_key: str, title: str, body: str) -> dict:
        raw = self.provider.create_page(space_key=space_key, title=title, body=body)
        return self._normalize_page(raw)

    def create_raw(self, *, space_key: str, title: str, body: str) -> dict:
        return self.provider.create_page(space_key=space_key, title=title, body=body)

    def update(self, page_id: str, *, title: str, body: str) -> dict:
        raw = self.provider.update_page(page_id=page_id, title=title, body=body)
        return self._normalize_page(raw)

    def update_raw(self, page_id: str, *, title: str, body: str) -> dict:
        return self.provider.update_page(page_id=page_id, title=title, body=body)

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)

    def delete_raw(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
