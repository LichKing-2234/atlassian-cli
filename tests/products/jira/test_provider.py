import pytest
from requests import HTTPError

from atlassian_cli.core.errors import (
    AuthError,
    ConflictError,
    NotFoundError,
    UnsupportedError,
    ValidationError,
)
from atlassian_cli.products.jira.providers.server import JiraServerProvider


def build_provider_with_client(client) -> JiraServerProvider:
    provider = JiraServerProvider.__new__(JiraServerProvider)
    provider.client = client
    return provider


def test_create_issues_wraps_bulk_fields_and_extracts_created_issues() -> None:
    calls: dict[str, object] = {}

    class FakeClient:
        def create_issues(self, issues: list[dict]) -> dict:
            calls["issues"] = issues
            return {"issues": [{"id": "10001", "key": "DEMO-1"}], "errors": []}

    fields = {
        "project": {"key": "DEMO"},
        "issuetype": {"name": "Task"},
        "summary": "Example issue summary",
    }

    result = build_provider_with_client(FakeClient()).create_issues([fields])

    assert calls["issues"] == [{"fields": fields}]
    assert result == [{"id": "10001", "key": "DEMO-1"}]


def test_create_issues_falls_back_to_single_create_on_server_error() -> None:
    calls: dict[str, object] = {"issue_create": []}

    class FakeResponse:
        status_code = 500

    class FakeClient:
        def create_issues(self, issues: list[dict]) -> list[dict]:
            calls["create_issues"] = issues
            raise HTTPError("Server error", response=FakeResponse())

        def issue_create(self, fields: dict) -> dict:
            cast_calls = calls["issue_create"]
            assert isinstance(cast_calls, list)
            cast_calls.append(fields)
            return {"key": f"DEMO-{len(cast_calls)}"}

    issues = [
        {"project": {"key": "DEMO"}, "issuetype": {"name": "Task"}, "summary": "one"},
        {"project": {"key": "DEMO"}, "issuetype": {"name": "Task"}, "summary": "two"},
    ]
    provider = build_provider_with_client(FakeClient())

    result = provider.create_issues(issues)

    assert result == [{"key": "DEMO-1"}, {"key": "DEMO-2"}]
    assert calls["create_issues"] == [{"fields": issue} for issue in issues]
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
                                "name": "Task",
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

    result = provider.get_field_options("priority", "TEST", "Task")

    assert result == [
        {"id": "1", "name": "Highest"},
        {"id": "2", "name": "High"},
    ]
    assert calls["args"] == ("TEST", "projects.issuetypes.fields")


def test_get_field_options_filters_values_before_applying_return_limit() -> None:
    class FakeClient:
        @staticmethod
        def issue_createmeta(project_key: str, expand: str) -> dict:
            return {
                "projects": [
                    {
                        "issuetypes": [
                            {
                                "name": "Task",
                                "fields": {
                                    "priority": {
                                        "allowedValues": [
                                            {"id": "1", "name": "Highest"},
                                            {"id": "2", "name": "High"},
                                            {"id": "3", "name": "Low"},
                                        ]
                                    }
                                },
                            }
                        ]
                    }
                ]
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.get_field_options("priority", "DEMO", "Task", contains="high", return_limit=1)

    assert result == [{"id": "1", "name": "Highest"}]


def test_get_issue_forwards_server_options_and_limits_newest_comments() -> None:
    calls = {}

    class FakeClient:
        def get_issue(self, issue_key, *, fields, properties, update_history, expand):
            calls["get_issue"] = {
                "issue_key": issue_key,
                "fields": fields,
                "properties": properties,
                "update_history": update_history,
                "expand": expand,
            }
            return {"key": issue_key, "fields": {"comment": {"comments": []}}}

        def issue_get_comments(self, issue_key: str) -> dict:
            calls["comments"] = issue_key
            return {
                "comments": [
                    {"id": "1", "body": "first"},
                    {"id": "2", "body": "second"},
                    {"id": "3", "body": "third"},
                ]
            }

    provider = build_provider_with_client(FakeClient())

    result = provider.get_issue(
        "DEMO-1",
        fields=["summary"],
        expand="renderedFields",
        comment_limit=2,
        properties=["triage", "ops"],
        update_history=False,
    )

    assert calls == {
        "get_issue": {
            "issue_key": "DEMO-1",
            "fields": ["summary", "comment"],
            "properties": "triage,ops",
            "update_history": False,
            "expand": "renderedFields",
        },
        "comments": "DEMO-1",
    }
    assert result["fields"]["comment"]["comments"] == [
        {"id": "2", "body": "second"},
        {"id": "3", "body": "third"},
    ]


def test_get_issue_keeps_issue_read_when_comment_fetch_fails() -> None:
    class FakeClient:
        @staticmethod
        def get_issue(issue_key, *, fields, properties, update_history, expand):
            del properties, update_history, expand
            assert issue_key == "DEMO-1"
            assert fields == ["summary", "comment"]
            return {"key": issue_key, "fields": {"comment": {"comments": []}}}

        @staticmethod
        def issue_get_comments(issue_key: str) -> dict:
            raise HTTPError(f"comments unavailable for {issue_key}")

    result = build_provider_with_client(FakeClient()).get_issue(
        "DEMO-1", fields=["summary"], comment_limit=2
    )

    assert result["key"] == "DEMO-1"
    assert result["fields"]["comment"]["comments"] == []


def test_search_users_uses_assignable_project_endpoint() -> None:
    calls = {}

    class FakeClient:
        @staticmethod
        def resource_url(path: str) -> str:
            calls["path"] = path
            return f"https://jira.example.com/rest/api/2/{path}"

        @staticmethod
        def get(url: str, *, params: dict) -> list[dict]:
            calls["request"] = (url, params)
            return [{"name": "example-user"}]

    provider = build_provider_with_client(FakeClient())

    result = provider.search_users("example", project_key="DEMO", issue_key=None, limit=12)

    assert result == [{"name": "example-user"}]
    assert calls == {
        "path": "user/assignable/search",
        "request": (
            "https://jira.example.com/rest/api/2/user/assignable/search",
            {"username": "example", "project": "DEMO", "maxResults": 12},
        ),
    }


def test_search_users_uses_assignable_issue_scope() -> None:
    calls = {}

    class FakeClient:
        @staticmethod
        def resource_url(path: str) -> str:
            return f"https://jira.example.com/rest/api/2/{path}"

        @staticmethod
        def get(url: str, *, params: dict) -> list[dict]:
            calls["request"] = (url, params)
            return []

    provider = build_provider_with_client(FakeClient())

    assert provider.search_users("example", project_key=None, issue_key="DEMO-1", limit=7) == []
    assert calls["request"] == (
        "https://jira.example.com/rest/api/2/user/assignable/search",
        {"username": "example", "issueKey": "DEMO-1", "maxResults": 7},
    )


def test_search_fields_filters_live_fields_before_applying_limit() -> None:
    class FakeClient:
        @staticmethod
        def get_all_fields() -> list[dict]:
            return [
                {"id": "customfield_10001", "name": "Story Points"},
                {"id": "customfield_10002", "name": "Story Estimate"},
                {"id": "summary", "name": "Summary"},
            ]

    provider = build_provider_with_client(FakeClient())

    result = provider.search_fields("story", limit=1)

    assert result == [{"id": "customfield_10001", "name": "Story Points"}]


def test_list_issue_attachments_fetches_attachment_field_only() -> None:
    calls = {}

    class FakeClient:
        def issue(self, issue_key: str, fields="*all", expand=None) -> dict:
            calls["args"] = (issue_key, fields, expand)
            return {"fields": {"attachment": [{"id": "10001", "filename": "report.pdf"}]}}

    provider = build_provider_with_client(FakeClient())

    result = provider.list_issue_attachments("DEMO-1")

    assert result == [{"id": "10001", "filename": "report.pdf"}]
    assert calls["args"] == ("DEMO-1", "attachment", None)


def test_upload_issue_attachment_delegates_to_client() -> None:
    calls = {}

    class FakeClient:
        def add_attachment(self, issue_key: str, filename: str) -> dict:
            calls["args"] = (issue_key, filename)
            return {"id": "10001", "filename": "report.pdf", "size": 42}

    provider = build_provider_with_client(FakeClient())

    result = provider.upload_issue_attachment("DEMO-1", "/tmp/report.pdf")

    assert result == {"id": "10001", "filename": "report.pdf", "size": 42}
    assert calls["args"] == ("DEMO-1", "/tmp/report.pdf")


def test_update_issue_uploads_attachments_separately_from_fields() -> None:
    calls = []

    class FakeClient:
        def issue_update(self, issue_key: str, *, fields: dict) -> None:
            calls.append(("update", issue_key, fields))

        def add_attachment(self, issue_key: str, filename: str) -> dict:
            calls.append(("attach", issue_key, filename))
            return {"id": "10001", "filename": "report.pdf", "size": 42}

    provider = build_provider_with_client(FakeClient())

    result = provider.update_issue(
        "DEMO-1",
        {"summary": "Updated summary"},
        attachments=["/tmp/report.pdf"],
    )

    assert calls == [
        ("update", "DEMO-1", {"summary": "Updated summary"}),
        ("attach", "DEMO-1", "/tmp/report.pdf"),
    ]
    assert result == {
        "key": "DEMO-1",
        "updated": True,
        "attachment_results": [{"id": "10001", "filename": "report.pdf", "size": 42}],
    }


def test_issue_link_methods_delegate_to_client() -> None:
    calls = []

    class FakeClient:
        def issue(self, issue_key: str, fields="*all", expand=None) -> dict:
            calls.append(("issue", issue_key, fields, expand))
            return {"fields": {"issuelinks": [{"id": "10001"}, "invalid"]}}

        def create_issue_link(self, data: dict) -> None:
            calls.append(("create", data))

        def remove_issue_link(self, link_id: str) -> None:
            calls.append(("delete", link_id))

        def get_issue_link_types(self) -> list[dict]:
            calls.append(("types",))
            return [{"id": "10000", "name": "Cloners"}]

    provider = build_provider_with_client(FakeClient())
    payload = {
        "type": {"name": "Cloners"},
        "inwardIssue": {"key": "DEMO-1"},
        "outwardIssue": {"key": "DEMO-1234"},
    }

    assert provider.list_issue_links("DEMO-1") == [{"id": "10001"}]
    assert provider.create_issue_link(payload) is None
    assert provider.delete_issue_link("10001") is None
    assert provider.get_issue_link_types() == [{"id": "10000", "name": "Cloners"}]
    assert calls == [
        ("issue", "DEMO-1", "issuelinks", None),
        ("create", payload),
        ("delete", "10001"),
        ("types",),
    ]


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, ValidationError),
        (401, AuthError),
        (403, AuthError),
        (404, NotFoundError),
        (409, ConflictError),
    ],
)
def test_issue_link_http_errors_are_actionable(status_code, error_type) -> None:
    class FakeResponse:
        def __init__(self, value: int) -> None:
            self.status_code = value

    class FakeClient:
        def create_issue_link(self, data: dict) -> None:
            raise HTTPError("example response", response=FakeResponse(status_code))

    provider = build_provider_with_client(FakeClient())

    with pytest.raises(error_type):
        provider.create_issue_link({"type": {"name": "Cloners"}})


def test_download_issue_attachment_streams_to_destination(tmp_path) -> None:
    calls = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 64 * 1024
            yield b"example "
            yield b"report\n"

    class FakeSession:
        def get(self, url: str, *, stream: bool):
            calls.append((url, stream))
            return FakeResponse()

    class FakeClient:
        _session = FakeSession()

    provider = build_provider_with_client(FakeClient())
    target = tmp_path / "report.pdf"

    result = provider.download_issue_attachment(
        {
            "id": "10001",
            "filename": "report.pdf",
            "content": "attachment://DEMO-1/report.pdf",
        },
        str(target),
        issue_key="DEMO-1",
    )

    assert target.read_bytes() == b"example report\n"
    assert result == {
        "issue_key": "DEMO-1",
        "attachment_id": "10001",
        "filename": "report.pdf",
        "path": str(target),
        "bytes_written": 15,
    }
    assert calls == [("attachment://DEMO-1/report.pdf", True)]


def test_reparent_subtask_submits_jira_711_move_workflow() -> None:
    calls = []

    class FakeResponse:
        def __init__(self, *, url: str, text: str) -> None:
            self.url = url
            self.text = text

        def raise_for_status(self) -> None:
            return None

    first = FakeResponse(
        url="https://jira.example.com/secure/MoveSubTaskChooseOperation!default.jspa?id=10003",
        text="""
        <form method="post" action="MoveSubTaskChooseOperation.jspa?atl_token=example&amp;id=10003">
          <input name="operation" value="move.subtask.parent.operation.name">
          <input name="atl_token" value="example response">
        </form>
        """,
    )
    second = FakeResponse(
        url="https://jira.example.com/secure/MoveSubTaskParent!default.jspa?id=10003",
        text="""
        <form method="post" action="MoveSubTaskParent.jspa?atl_token=example&amp;id=10003">
          <input name="parentIssue">
          <input name="id" value="10003">
          <input name="atl_token" value="example response">
        </form>
        """,
    )
    final = FakeResponse(url="https://jira.example.com/browse/DEMO-1234", text="")

    class FakeSession:
        def get(self, url: str, *, params: dict):
            calls.append(("get", url, params))
            return first

        def post(self, url: str, *, data: dict):
            calls.append(("post", url, data))
            return second if len(calls) == 2 else final

    class FakeClient:
        url = "https://jira.example.com"
        _session = FakeSession()

        def get_server_info(self) -> dict:
            return {"version": "7.11.0", "buildNumber": "711000"}

    provider = build_provider_with_client(FakeClient())

    provider.reparent_subtask("10003", "DEMO-1")

    assert calls[0] == (
        "get",
        "https://jira.example.com/secure/MoveSubTaskChooseOperation!default.jspa",
        {"id": "10003"},
    )
    assert calls[1][2] == {
        "operation": "move.subtask.parent.operation.name",
        "atl_token": "example response",
    }
    assert calls[2][2] == {
        "parentIssue": "DEMO-1",
        "id": "10003",
        "atl_token": "example response",
    }
    assert all("/subtask/move" not in call[1] for call in calls)


def test_reparent_subtask_rejects_unrecognized_jira_build_before_workflow() -> None:
    class FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("unsupported builds must not start the workflow")

    class FakeClient:
        url = "https://jira.example.com"
        _session = FakeSession()

        def get_server_info(self) -> dict:
            return {"version": "7.11.1", "buildNumber": "711001"}

    provider = build_provider_with_client(FakeClient())

    with pytest.raises(UnsupportedError, match="only Jira Server 7.11.0 build 711000"):
        provider.reparent_subtask("10003", "DEMO-1")


def test_reparent_subtask_rejects_cross_origin_form_action() -> None:
    class FakeResponse:
        url = "https://jira.example.com/secure/MoveSubTaskChooseOperation!default.jspa"
        text = """
        <form method="post" action="https://other.example.com/MoveSubTaskChooseOperation.jspa">
          <input name="operation" value="move.subtask.parent.operation.name">
          <input name="atl_token" value="example response">
        </form>
        """

    with pytest.raises(UnsupportedError, match="not same-origin"):
        JiraServerProvider._reparent_form(
            FakeResponse(),
            field="operation",
            action_name="MoveSubTaskChooseOperation.jspa",
        )


def test_reparent_subtask_reports_permission_failure() -> None:
    class ForbiddenResponse:
        status_code = 403
        url = "https://jira.example.com/secure/MoveSubTaskChooseOperation!default.jspa"
        text = ""

        def raise_for_status(self) -> None:
            raise HTTPError("forbidden", response=self)

    class FakeSession:
        def get(self, url: str, *, params: dict):
            return ForbiddenResponse()

    class FakeClient:
        url = "https://jira.example.com"
        _session = FakeSession()

        def get_server_info(self) -> dict:
            return {"version": "7.11.0", "buildNumber": "711000"}

    provider = build_provider_with_client(FakeClient())

    with pytest.raises(AuthError, match="Move Issues permission"):
        provider.reparent_subtask("10003", "DEMO-1")
