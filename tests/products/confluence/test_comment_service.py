from atlassian_cli.products.confluence.services.comment import CommentService


class FakeCommentProvider:
    def list_comments(self, page_id: str) -> list[dict]:
        assert page_id == "1234"
        return [
            {
                "id": "c1",
                "body": {"storage": {"value": "LGTM"}},
                "history": {"createdDate": "2026-04-28"},
            }
        ]

    def add_comment(self, page_id: str, body: str) -> dict:
        assert page_id == "1234"
        return {"id": "c2", "body": {"storage": {"value": body}}}

    def reply_to_comment(self, comment_id: str, body: str) -> dict:
        assert comment_id == "c1"
        return {"id": "c3", "body": {"storage": {"value": body}}}


def test_comment_service_list_normalizes_results() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.list("1234")

    assert result["results"][0]["id"] == "c1"


def test_comment_service_add_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.add("1234", "ship it")

    assert result["id"] == "c2"
    assert result["body"] == "ship it"


def test_comment_service_reply_normalizes_result() -> None:
    service = CommentService(provider=FakeCommentProvider())

    result = service.reply("c1", "ack")

    assert result["id"] == "c3"
    assert result["body"] == "ack"
