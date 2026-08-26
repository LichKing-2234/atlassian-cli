import pytest

from atlassian_cli.core.errors import ConflictError, ValidationError
from atlassian_cli.products.jira.services.remote_link import RemoteIssueLinkService


def test_remote_link_service_builds_payload_and_reads_created_link() -> None:
    calls = {}

    class FakeProvider:
        def create_remote_issue_link(self, issue_key: str, data: dict) -> dict:
            calls["create"] = (issue_key, data)
            return {"id": 10001, "self": "DEMO"}

        def get_remote_issue_link(self, issue_key: str, link_id: str) -> dict:
            calls["get"] = (issue_key, link_id)
            return {
                "id": 10001,
                "relationship": "example comment",
                "object": {
                    "url": "https://example.com/DEMO-1",
                    "title": "Example Page",
                    "summary": "example response",
                    "icon": {
                        "url16x16": "https://example.com/DEMO-1234",
                        "title": "Example Page",
                    },
                },
            }

    service = RemoteIssueLinkService(provider=FakeProvider())

    result = service.create(
        "DEMO-1",
        url="https://example.com/DEMO-1",
        title="Example Page",
        summary="example response",
        relationship="example comment",
        icon_url="https://example.com/DEMO-1234",
    )

    assert calls == {
        "create": (
            "DEMO-1",
            {
                "object": {
                    "url": "https://example.com/DEMO-1",
                    "title": "Example Page",
                    "summary": "example response",
                    "icon": {
                        "url16x16": "https://example.com/DEMO-1234",
                        "title": "Example Page",
                    },
                },
                "relationship": "example comment",
            },
        ),
        "get": ("DEMO-1", "10001"),
    }
    assert result == {
        "issue_key": "DEMO-1",
        "id": "10001",
        "url": "https://example.com/DEMO-1",
        "title": "Example Page",
        "summary": "example response",
        "relationship": "example comment",
        "icon_url": "https://example.com/DEMO-1234",
    }


def test_remote_link_service_raw_create_preserves_jira_responses() -> None:
    class FakeProvider:
        def create_remote_issue_link(self, issue_key: str, data: dict) -> dict:
            return {"id": 10001, "self": "DEMO"}

        def get_remote_issue_link(self, issue_key: str, link_id: str) -> dict:
            return {
                "id": 10001,
                "object": {
                    "url": "https://example.com/DEMO-1",
                    "title": "Example Page",
                },
            }

    service = RemoteIssueLinkService(provider=FakeProvider())

    result = service.create_raw(
        "DEMO-1",
        url="https://example.com/DEMO-1",
        title="Example Page",
    )

    assert result == {
        "create_response": {"id": 10001, "self": "DEMO"},
        "remote_link_response": {
            "id": 10001,
            "object": {
                "url": "https://example.com/DEMO-1",
                "title": "Example Page",
            },
        },
    }


@pytest.mark.parametrize(
    ("issue_key", "url", "title", "expected"),
    [
        ("", "https://example.com/DEMO-1", "Example Page", "issue key is required"),
        ("DEMO-1", "", "Example Page", "URL is required"),
        ("DEMO-1", "https://example.com/DEMO-1", "", "title is required"),
    ],
)
def test_remote_link_service_rejects_empty_required_inputs_before_http(
    issue_key: str, url: str, title: str, expected: str
) -> None:
    class FailProvider:
        def create_remote_issue_link(self, *_args, **_kwargs) -> dict:
            raise AssertionError("HTTP must not run for invalid input")

    service = RemoteIssueLinkService(provider=FailProvider())

    with pytest.raises(ValidationError, match=expected):
        service.create(issue_key, url=url, title=title)


def test_remote_link_service_rejects_mismatched_readback() -> None:
    class FakeProvider:
        def create_remote_issue_link(self, issue_key: str, data: dict) -> dict:
            return {"id": 10001}

        def get_remote_issue_link(self, issue_key: str, link_id: str) -> dict:
            return {
                "id": 10001,
                "object": {
                    "url": "https://example.com/DEMO-1",
                    "title": "example response",
                },
            }

    service = RemoteIssueLinkService(provider=FakeProvider())

    with pytest.raises(ConflictError, match="did not match"):
        service.create(
            "DEMO-1",
            url="https://example.com/DEMO-1",
            title="Example Page",
        )
