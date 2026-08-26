import pytest

from atlassian_cli.products.jira.services.comment import CommentService


class FakeCommentProvider:
    def __init__(self) -> None:
        self.calls = []

    def add_comment(
        self, issue_key: str, body: str, visibility: dict[str, str] | None = None
    ) -> dict:
        assert issue_key == "DEMO-1"
        self.calls.append(("add", body, visibility))
        return {"id": "10001", "body": body, "author": {"displayName": "Example Author"}}

    def edit_comment(
        self,
        issue_key: str,
        comment_id: str,
        body: str,
        visibility: dict[str, str] | None = None,
    ) -> dict:
        assert issue_key == "DEMO-1"
        assert comment_id == "10001"
        self.calls.append(("edit", body, visibility))
        return {"id": comment_id, "body": body, "author": {"displayName": "Example Author"}}


def test_comment_service_add_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.add("DEMO-1", "Looks good")

    assert result == {
        "id": "10001",
        "body": "Looks good",
        "author": {"display_name": "Example Author", "name": "Example Author"},
    }


def test_comment_service_add_forwards_visibility() -> None:
    provider = FakeCommentProvider()
    service = CommentService(provider=provider)

    service.add(
        "DEMO-1",
        "example comment",
        visibility={"type": "group", "value": "reviewer-one"},
    )

    assert provider.calls == [
        ("add", "example comment", {"type": "group", "value": "reviewer-one"})
    ]


def test_comment_service_add_converts_default_markdown_to_jira_markup() -> None:
    provider = FakeCommentProvider()

    CommentService(provider=provider).add(
        "DEMO-1",
        "## Example Page\n\n**example response**",
    )

    assert provider.calls == [("add", "h2. Example Page\n\n*example response*", None)]


def test_comment_service_rejects_unknown_body_format_before_write() -> None:
    provider = FakeCommentProvider()

    with pytest.raises(ValueError, match="body_format must be 'markdown' or 'jira'"):
        CommentService(provider=provider).add(
            "DEMO-1",
            "example comment",
            body_format="html",
        )

    assert provider.calls == []


def test_comment_service_edit_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.edit("DEMO-1", "10001", "Updated")

    assert result == {
        "id": "10001",
        "body": "Updated",
        "author": {"display_name": "Example Author", "name": "Example Author"},
    }


def test_comment_service_edit_forwards_visibility() -> None:
    provider = FakeCommentProvider()
    service = CommentService(provider=provider)

    service.edit(
        "DEMO-1",
        "10001",
        "example response",
        visibility={"type": "role", "value": "reviewer-one"},
    )

    assert provider.calls == [
        ("edit", "example response", {"type": "role", "value": "reviewer-one"})
    ]


def test_comment_service_edit_converts_default_markdown_to_jira_markup() -> None:
    provider = FakeCommentProvider()

    CommentService(provider=provider).edit(
        "DEMO-1",
        "10001",
        "### Example Page\n\n`example response`",
    )

    assert provider.calls == [("edit", "h3. Example Page\n\n{{example response}}", None)]


@pytest.mark.parametrize("operation", ["add", "edit"])
def test_comment_service_preserves_explicit_jira_markup(operation: str) -> None:
    provider = FakeCommentProvider()
    service = CommentService(provider=provider)
    body = "h2. Example Page\n\n{code}example response{code}"

    if operation == "add":
        service.add("DEMO-1", body, body_format="jira")
    else:
        service.edit("DEMO-1", "10001", body, body_format="jira")

    assert provider.calls == [(operation, body, None)]
