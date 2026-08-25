import pytest
from requests import HTTPError

from atlassian_cli.core.errors import AuthError, ConflictError, NotFoundError, ValidationError
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
