from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraComment


class CommentService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def add(self, issue_key: str, body: str) -> dict:
        return JiraComment.from_api_response(
            self.provider.add_comment(issue_key, body)
        ).to_simplified_dict()

    def add_raw(self, issue_key: str, body: str) -> dict:
        return self.provider.add_comment(issue_key, body)

    def edit(self, issue_key: str, comment_id: str, body: str) -> dict:
        return JiraComment.from_api_response(
            self.provider.edit_comment(issue_key, comment_id, body)
        ).to_simplified_dict()

    def edit_raw(self, issue_key: str, comment_id: str, body: str) -> dict:
        return self.provider.edit_comment(issue_key, comment_id, body)
