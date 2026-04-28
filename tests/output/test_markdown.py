from atlassian_cli.output.markdown import (
    render_markdown,
    render_markdown_list_item,
    render_markdown_preview,
)


def test_render_markdown_formats_single_resource_detail() -> None:
    payload = {
        "key": "OPS-1",
        "summary": "Broken deploy",
        "status": {"name": "Open"},
        "description": "Investigate the release pipeline",
    }

    rendered = render_markdown(payload)

    assert rendered.startswith("# OPS-1 - Broken deploy")
    assert "- Status: Open" in rendered
    assert "## Description" in rendered
    assert "Investigate the release pipeline" in rendered


def test_render_markdown_formats_results_envelope_as_numbered_summary() -> None:
    payload = {
        "results": [
            {
                "id": 42,
                "title": "Ship output cleanup",
                "state": "OPEN",
                "author": {"display_name": "Alice"},
                "reviewers": ["Bob", "Carol", "Dave", "Eve"],
            }
        ]
    }

    rendered = render_markdown(payload)

    assert "1. 42 - Ship output cleanup" in rendered
    assert "- State: OPEN" in rendered
    assert "- Author: Alice" in rendered
    assert "- Reviewers: Bob, Carol, Dave, +1 more" in rendered


def test_render_markdown_list_item_returns_single_scan_line() -> None:
    item = {
        "key": "OPS-1",
        "summary": "Broken deploy",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Alice"},
    }

    rendered = render_markdown_list_item(item)

    assert rendered == "OPS-1  Open  Alice  Broken deploy"


def test_render_markdown_preview_limits_description_excerpt() -> None:
    item = {
        "key": "OPS-1",
        "summary": "Broken deploy",
        "status": {"name": "Open"},
        "assignee": {"display_name": "Alice"},
        "description": "Line one\nLine two\nLine three\nLine four",
        "links": {"self": "https://example.com"},
    }

    rendered = render_markdown_preview(item)

    assert "Status: Open" in rendered
    assert "Assignee: Alice" in rendered
    assert "Line four" not in rendered
    assert "links" not in rendered.lower()
