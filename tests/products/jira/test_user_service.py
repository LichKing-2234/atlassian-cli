from atlassian_cli.products.jira.services.user import UserService


def test_user_service_search_forwards_assignable_scope_and_limit() -> None:
    calls = {}

    class FakeProvider:
        def search_users(self, query, *, project_key, issue_key, limit):
            calls["args"] = (query, project_key, issue_key, limit)
            return [{"displayName": "Example Author", "name": "example-user"}]

    result = UserService(provider=FakeProvider()).search(
        "example", project_key="DEMO", issue_key=None, limit=12
    )

    assert calls["args"] == ("example", "DEMO", None, 12)
    assert result == {"results": [{"display_name": "Example Author", "name": "example-user"}]}


def test_user_service_search_covers_project_and_issue_scopes() -> None:
    calls = []

    class FakeProvider:
        def search_users(self, query, *, project_key, issue_key, limit):
            calls.append((query, project_key, issue_key, limit))
            return []

    service = UserService(provider=FakeProvider())

    service.search("Example Author", project_key="DEMO", issue_key=None, limit=12)
    service.search("Example Collaborator", project_key=None, issue_key="DEMO-1", limit=7)

    assert calls == [
        ("Example Author", "DEMO", None, 12),
        ("Example Collaborator", None, "DEMO-1", 7),
    ]
