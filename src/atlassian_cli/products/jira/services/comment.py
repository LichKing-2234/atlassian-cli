from atlassian_cli.products.jira.markup import markdown_to_jira
from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraComment


class CommentService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    @staticmethod
    def _prepare_body(body: str, body_format: str) -> str:
        if body_format not in {"markdown", "jira"}:
            raise ValueError("body_format must be 'markdown' or 'jira'")
        return markdown_to_jira(body) if body_format == "markdown" else body

    def add(
        self,
        issue_key: str,
        body: str,
        *,
        visibility: dict[str, str] | None = None,
        body_format: str = "markdown",
    ) -> dict:
        return JiraComment.from_api_response(
            self.provider.add_comment(issue_key, self._prepare_body(body, body_format), visibility)
        ).to_simplified_dict()

    def add_raw(
        self,
        issue_key: str,
        body: str,
        *,
        visibility: dict[str, str] | None = None,
        body_format: str = "markdown",
    ) -> dict:
        return self.provider.add_comment(
            issue_key, self._prepare_body(body, body_format), visibility
        )

    def edit(
        self,
        issue_key: str,
        comment_id: str,
        body: str,
        *,
        visibility: dict[str, str] | None = None,
        body_format: str = "markdown",
    ) -> dict:
        return JiraComment.from_api_response(
            self.provider.edit_comment(
                issue_key,
                comment_id,
                self._prepare_body(body, body_format),
                visibility,
            )
        ).to_simplified_dict()

    def edit_raw(
        self,
        issue_key: str,
        comment_id: str,
        body: str,
        *,
        visibility: dict[str, str] | None = None,
        body_format: str = "markdown",
    ) -> dict:
        return self.provider.edit_comment(
            issue_key,
            comment_id,
            self._prepare_body(body, body_format),
            visibility,
        )
