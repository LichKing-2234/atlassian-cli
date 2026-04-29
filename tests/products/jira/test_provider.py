from requests import HTTPError

from atlassian_cli.products.jira.providers.server import JiraServerProvider


def build_provider_with_client(client) -> JiraServerProvider:
    provider = JiraServerProvider.__new__(JiraServerProvider)
    provider.client = client
    return provider


def test_create_issues_falls_back_to_single_create_on_server_error() -> None:
    calls: dict[str, object] = {"issue_create": []}

    class FakeResponse:
        status_code = 500

    class FakeClient:
        def create_issues(self, issues: list[dict]) -> list[dict]:
            calls["create_issues"] = issues
            raise HTTPError("内部服务器错误", response=FakeResponse())

        def issue_create(self, fields: dict) -> dict:
            cast_calls = calls["issue_create"]
            assert isinstance(cast_calls, list)
            cast_calls.append(fields)
            return {"key": f"EEP-{len(cast_calls)}"}

    issues = [
        {"project": {"key": "EEP"}, "issuetype": {"name": "Task"}, "summary": "one"},
        {"project": {"key": "EEP"}, "issuetype": {"name": "Task"}, "summary": "two"},
    ]
    provider = build_provider_with_client(FakeClient())

    result = provider.create_issues(issues)

    assert result == [{"key": "EEP-1"}, {"key": "EEP-2"}]
    assert calls["create_issues"] == issues
    assert calls["issue_create"] == issues


def test_get_field_options_filters_issue_type_by_name() -> None:
    calls = {}

    class FakeClient:
        def issue_createmeta(self, project_key: str, expand: str):
            calls["args"] = (project_key, expand)
            return {
                "projects": [
                    {
                        "issuetypes": [
                            {
                                "id": "10002",
                                "name": "任务",
                                "fields": {
                                    "priority": {
                                        "allowedValues": [
                                            {"id": "1", "name": "Highest"},
                                            {"id": "2", "name": "High"},
                                        ]
                                    }
                                },
                            }
                        ]
                    }
                ]
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.get_field_options("priority", "EEP", "任务")

    assert result == [
        {"id": "1", "name": "Highest"},
        {"id": "2", "name": "High"},
    ]
    assert calls["args"] == ("EEP", "projects.issuetypes.fields")
