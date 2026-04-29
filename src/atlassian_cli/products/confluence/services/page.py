from collections import deque
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

    def _page_envelope(
        self,
        payload: dict,
        *,
        include_metadata: bool = True,
        include_content: bool = True,
    ) -> dict:
        page = ConfluencePage.from_api_response(payload, **self._page_kwargs())
        result: dict[str, object] = {}
        if include_metadata:
            result["metadata"] = page.to_simplified_dict()
        if include_content and page.content not in (None, ""):
            result["content"] = {"value": page.content}
        return result

    def get(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = False,
    ) -> dict:
        raw = self.provider.get_page(
            page_id,
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )
        return self._page_envelope(raw, include_metadata=include_metadata, include_content=True)

    def get_raw(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = False,
    ) -> dict:
        return self.provider.get_page(
            page_id,
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )

    def get_by_title(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = False,
    ) -> dict | None:
        page = self.provider.get_page_by_title(
            space_key,
            title,
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )
        if page is None:
            return None
        return self._page_envelope(page, include_metadata=include_metadata, include_content=True)

    def get_by_title_raw(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = False,
    ) -> dict | None:
        return self.provider.get_page_by_title(
            space_key,
            title,
            include_metadata=include_metadata,
            convert_to_markdown=convert_to_markdown,
        )

    def search(self, query: str, *, limit: int, spaces_filter: list[str] | None = None) -> dict:
        return {
            "results": [
                self._normalize_page(item)
                for item in self.provider.search_pages(
                    query, limit=limit, spaces_filter=spaces_filter
                )
            ]
        }

    def search_raw(
        self, query: str, *, limit: int, spaces_filter: list[str] | None = None
    ) -> list[dict]:
        return self.provider.search_pages(query, limit=limit, spaces_filter=spaces_filter)

    def children(self, page_id: str) -> dict:
        return {
            "results": [
                self._normalize_page(item) for item in self.provider.get_page_children(page_id)
            ]
        }

    def children_raw(self, page_id: str) -> list[dict]:
        return self.provider.get_page_children(page_id)

    def tree(self, space_key: str) -> dict:
        root = self.provider.get_space_homepage(space_key)
        results: list[dict] = []
        queue = deque([(root, 0)])

        while queue:
            page, depth = queue.popleft()
            normalized = self._normalize_page(page)
            normalized["depth"] = depth
            results.append(normalized)
            for child in self.provider.get_page_children(str(page.get("id", ""))):
                queue.append((child, depth + 1))

        return {"results": results}

    def tree_raw(self, space_key: str) -> dict:
        return self.tree(space_key)

    def history(
        self,
        page_id: str,
        *,
        version: int,
        convert_to_markdown: bool = False,
    ) -> dict:
        raw = self.provider.get_page_version(
            page_id, version, convert_to_markdown=convert_to_markdown
        )
        return self._page_envelope(raw, include_metadata=True, include_content=True)

    def history_raw(
        self,
        page_id: str,
        *,
        version: int,
        convert_to_markdown: bool = False,
    ) -> dict:
        return self.provider.get_page_version(
            page_id, version, convert_to_markdown=convert_to_markdown
        )

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

    def create(
        self,
        *,
        space_key: str,
        title: str,
        content: str,
        parent_id: str | None = None,
        content_format: str = "storage",
        enable_heading_anchors: bool = False,
        include_content: bool = False,
        emoji: str | None = None,
    ) -> dict:
        raw = self.provider.create_page(
            space_key=space_key,
            title=title,
            body=content,
            parent_id=parent_id,
            content_format=content_format,
            enable_heading_anchors=enable_heading_anchors,
            emoji=emoji,
        )
        page = (
            self._page_envelope(raw, include_metadata=True, include_content=True)
            if include_content
            else self._normalize_page(raw)
        )
        return {"message": "Page created successfully", "page": page}

    def create_raw(
        self,
        *,
        space_key: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "storage",
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict:
        return self.provider.create_page(
            space_key=space_key,
            title=title,
            body=body,
            parent_id=parent_id,
            content_format=content_format,
            enable_heading_anchors=enable_heading_anchors,
            emoji=emoji,
        )

    def update(
        self,
        page_id: str,
        *,
        title: str,
        content: str,
        parent_id: str | None = None,
        content_format: str = "storage",
        is_minor_edit: bool = False,
        version_comment: str | None = None,
        enable_heading_anchors: bool = False,
        include_content: bool = False,
        emoji: str | None = None,
    ) -> dict:
        raw = self.provider.update_page(
            page_id=page_id,
            title=title,
            body=content,
            parent_id=parent_id,
            content_format=content_format,
            is_minor_edit=is_minor_edit,
            version_comment=version_comment,
            enable_heading_anchors=enable_heading_anchors,
            emoji=emoji,
        )
        page = (
            self._page_envelope(raw, include_metadata=True, include_content=True)
            if include_content
            else self._normalize_page(raw)
        )
        return {"message": "Page updated successfully", "page": page}

    def update_raw(
        self,
        page_id: str,
        *,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "storage",
        is_minor_edit: bool = False,
        version_comment: str | None = None,
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict:
        return self.provider.update_page(
            page_id=page_id,
            title=title,
            body=body,
            parent_id=parent_id,
            content_format=content_format,
            is_minor_edit=is_minor_edit,
            version_comment=version_comment,
            enable_heading_anchors=enable_heading_anchors,
            emoji=emoji,
        )

    def delete(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)

    def delete_raw(self, page_id: str) -> dict:
        return self.provider.delete_page(page_id)
