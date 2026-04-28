from atlassian_cli.products.jira.providers.base import JiraProvider
from atlassian_cli.products.jira.schemas import JiraField


class FieldService:
    def __init__(self, provider: JiraProvider) -> None:
        self.provider = provider

    def search(self, query: str) -> dict:
        return {
            "results": [
                JiraField.from_api_response(item).to_simplified_dict()
                for item in self.provider.search_fields(query)
            ]
        }

    def search_raw(self, query: str) -> list[dict]:
        return self.provider.search_fields(query)

    def options(self, field_id: str, *, project_key: str, issue_type: str) -> dict:
        return {
            "results": self.provider.get_field_options(
                field_id, project_key=project_key, issue_type=issue_type
            )
        }

    def options_raw(self, field_id: str, *, project_key: str, issue_type: str) -> list[dict]:
        return self.provider.get_field_options(field_id, project_key, issue_type)
