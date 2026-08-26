from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraField


class FieldService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def search(self, keyword: str, *, limit: int) -> dict:
        return {
            "results": [
                JiraField.from_api_response(item).to_simplified_dict()
                for item in self.provider.search_fields(keyword, limit=limit)
            ]
        }

    def search_raw(self, keyword: str, *, limit: int) -> list[dict]:
        return self.provider.search_fields(keyword, limit=limit)

    def options(
        self,
        field_id: str,
        *,
        project_key: str,
        issue_type: str,
        contains: str | None,
        return_limit: int,
    ) -> dict:
        return {
            "results": self.provider.get_field_options(
                field_id,
                project_key=project_key,
                issue_type=issue_type,
                contains=contains,
                return_limit=return_limit,
            )
        }

    def options_raw(
        self,
        field_id: str,
        *,
        project_key: str,
        issue_type: str,
        contains: str | None,
        return_limit: int,
    ) -> list[dict]:
        return self.provider.get_field_options(
            field_id,
            project_key,
            issue_type,
            contains=contains,
            return_limit=return_limit,
        )
