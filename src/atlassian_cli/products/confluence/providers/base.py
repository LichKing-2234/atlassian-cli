from typing import Protocol


class ConfluenceProvider(Protocol):
    def get_page(
        self,
        page_id: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict: ...
    def get_page_by_title(
        self,
        space_key: str,
        title: str,
        *,
        include_metadata: bool = True,
        convert_to_markdown: bool = True,
    ) -> dict | None: ...
    def search_pages(
        self,
        query: str,
        limit: int,
        *,
        spaces_filter: list[str] | None = None,
    ) -> list[dict]: ...
    def get_page_children(self, page_id: str) -> list[dict]: ...
    def get_space_homepage(self, space_key: str) -> dict: ...
    def move_page(
        self,
        page_id: str,
        target_parent_id: str | None = None,
        target_space_key: str | None = None,
        position: str = "append",
    ) -> dict: ...
    def get_page_version(
        self,
        page_id: str,
        version: int,
        *,
        convert_to_markdown: bool = True,
    ) -> dict: ...
    def create_page(
        self,
        *,
        space_key: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "markdown",
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict: ...
    def update_page(
        self,
        *,
        page_id: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        content_format: str = "markdown",
        is_minor_edit: bool = False,
        version_comment: str | None = None,
        enable_heading_anchors: bool = False,
        emoji: str | None = None,
    ) -> dict: ...
    def delete_page(self, page_id: str) -> dict: ...
    def list_spaces(self, *, start: int, limit: int) -> dict: ...
    def get_space(self, space_key: str) -> dict: ...
    def list_comments(self, page_id: str) -> list[dict]: ...
    def add_comment(self, page_id: str, body: str) -> dict: ...
    def reply_to_comment(self, comment_id: str, body: str) -> dict: ...
    def list_attachments(self, page_id: str) -> dict: ...
    def upload_attachment(self, page_id: str, file_path: str) -> dict: ...
    def download_attachment(self, attachment_id: str, destination: str) -> dict: ...
