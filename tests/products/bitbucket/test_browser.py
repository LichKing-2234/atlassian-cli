from atlassian_cli.products.bitbucket.browser import (
    render_pull_request_item,
    render_pull_request_preview,
)


def test_render_pull_request_item_uses_dense_single_line_format() -> None:
    item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "example-author"},
        "title": "[FEAT] ENG-12345 add configurable mic test",
    }

    rendered = render_pull_request_item(1, item)

    assert rendered == "24990  OPEN  example-author  [FEAT] ENG-12345 add configurable mic test"
    assert "\n" not in rendered


def test_render_pull_request_preview_summarizes_reviewers_and_description() -> None:
    item = {
        "id": 24990,
        "state": "OPEN",
        "author": {"display_name": "example-author"},
        "reviewers": [
            {"display_name": "Alice", "approved": True},
            {"display_name": "Bob", "approved": False},
            {"display_name": "Carol", "approved": False},
            {"display_name": "Dave", "approved": False},
        ],
        "from_ref": {"display_id": "jira/ENG-12345/release/4.5"},
        "to_ref": {"display_id": "release/4.5"},
        "updated_date": "2026-04-27T13:19:55+00:00",
        "description": "Line one\nLine two\nLine three\nLine four",
        "participants": [{"role": "PARTICIPANT"}],
        "links": {"self": "https://example.com/pr/24990"},
    }

    rendered = render_pull_request_preview(item)

    assert "Reviewers: Alice, Bob, Carol, +1 more" in rendered
    assert "From: jira/ENG-12345/release/4.5" in rendered
    assert "To: release/4.5" in rendered
    assert "Updated: 2026-04-27 13:19:55" in rendered
    assert "Line four" not in rendered
    assert "participants" not in rendered.lower()
    assert "links" not in rendered.lower()
