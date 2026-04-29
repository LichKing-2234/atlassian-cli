from atlassian_cli.output.markdown import (
    render_markdown,
    render_markdown_list_item,
    render_markdown_preview,
)


def test_render_markdown_formats_single_resource_detail() -> None:
    payload = {
        "key": "DEMO-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "description": "Investigate the release pipeline",
    }

    rendered = render_markdown(payload)

    assert rendered.startswith("# DEMO-1 - Example issue summary")
    assert "- Status: Open" in rendered
    assert "## Description" in rendered
    assert "Investigate the release pipeline" in rendered


def test_render_markdown_formats_results_envelope_as_numbered_summary() -> None:
    payload = {
        "results": [
            {
                "id": 42,
                "title": "Example pull request",
                "state": "OPEN",
                "author": {"display_name": "Example Author"},
                "reviewers": ["reviewer-one", "reviewer-two", "reviewer-three", "reviewer-four"],
            }
        ]
    }

    rendered = render_markdown(payload)

    assert "1. 42 - Example pull request" in rendered
    assert "- State: OPEN" in rendered
    assert "- Author: Example Author" in rendered
    assert "- Reviewers: reviewer-one, reviewer-two, reviewer-three, +1 more" in rendered


def test_render_markdown_list_item_returns_single_scan_line() -> None:
    item = {
        "key": "DEMO-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Example Author"},
    }

    rendered = render_markdown_list_item(item)

    assert rendered == "DEMO-1  Open  Example Author  Example issue summary"


def test_render_markdown_preview_limits_description_excerpt() -> None:
    item = {
        "key": "DEMO-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Example Author"},
        "description": "Line one\nLine two\nLine three\nLine four",
        "links": {"self": "https://example.com"},
    }

    rendered = render_markdown_preview(item)

    assert "Status: Open" in rendered
    assert "Assignee: Example Author" in rendered
    assert "Line four" not in rendered
    assert "links" not in rendered.lower()
