from atlassian_cli.products.jira.services.comment import CommentService


class FakeCommentProvider:
    def add_comment(self, issue_key: str, body: str) -> dict:
        assert issue_key == "DEMO-1"
        return {"id": "10001", "body": body, "author": {"displayName": "Example Author"}}

    def edit_comment(self, issue_key: str, comment_id: str, body: str) -> dict:
        assert issue_key == "DEMO-1"
        assert comment_id == "10001"
        return {"id": comment_id, "body": body, "author": {"displayName": "Example Author"}}


def test_comment_service_add_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.add("DEMO-1", "Looks good")

    assert result == {
        "id": "10001",
        "body": "Looks good",
        "author": {"display_name": "Example Author", "name": "Example Author"},
    }


def test_comment_service_edit_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.edit("DEMO-1", "10001", "Updated")

    assert result == {
        "id": "10001",
        "body": "Updated",
        "author": {"display_name": "Example Author", "name": "Example Author"},
    }
