import pytest
from requests import HTTPError

from atlassian_cli.core.errors import AuthError, UnsupportedError
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


def test_get_issue_rejects_unsupported_server_options() -> None:
    class FakeClient:
        def issue(self, issue_key: str, fields="*all", expand=None) -> dict:
            raise AssertionError(
                "should not call client.issue when unsupported options are requested"
            )

    provider = build_provider_with_client(FakeClient())

    try:
        provider.get_issue("DEMO-1", comment_limit=5)
    except NotImplementedError as exc:
        assert "comment_limit" in str(exc)
    else:
        raise AssertionError("expected NotImplementedError")


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
