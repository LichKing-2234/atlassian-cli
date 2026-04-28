from __future__ import annotations

from atlassian_cli.products.confluence.providers.base import ConfluenceProvider
from atlassian_cli.products.confluence.schemas import ConfluenceComment


class CommentService:
    def __init__(self, provider: ConfluenceProvider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> dict:
        return {
            "results": [
                ConfluenceComment.from_api_response(item).to_simplified_dict()
                for item in self.provider.list_comments(page_id)
            ]
        }

    def list_raw(self, page_id: str) -> list[dict]:
        return self.provider.list_comments(page_id)

    def add(self, page_id: str, body: str) -> dict:
        return ConfluenceComment.from_api_response(
            self.provider.add_comment(page_id, body)
        ).to_simplified_dict()

    def add_raw(self, page_id: str, body: str) -> dict:
        return self.provider.add_comment(page_id, body)

    def reply(self, comment_id: str, body: str) -> dict:
        return ConfluenceComment.from_api_response(
            self.provider.reply_to_comment(comment_id, body)
        ).to_simplified_dict()

    def reply_raw(self, comment_id: str, body: str) -> dict:
        return self.provider.reply_to_comment(comment_id, body)
