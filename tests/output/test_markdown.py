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


def test_render_markdown_unwraps_message_plus_issue_envelope() -> None:
    rendered = render_markdown(
        {
            "message": "Issue created successfully",
            "issue": {
                "key": "DEMO-1",
                "summary": "Example issue summary",
                "status": {"name": "Open"},
            },
        }
    )

    assert rendered.startswith("# DEMO-1 - Example issue summary")
    assert "- Status: Open" in rendered


def test_render_markdown_renders_page_metadata_and_content_envelope() -> None:
    rendered = render_markdown(
        {
            "metadata": {"id": "1234", "title": "Example Page", "version": 2},
            "content": {"value": "## Runbook\n\nUse the checklist."},
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
    assert "Use the checklist." in rendered


def test_render_markdown_converts_confluence_storage_html_content() -> None:
    rendered = render_markdown(
        {
            "metadata": {"id": "1234", "title": "Example Page", "version": 2},
            "content": {
                "value": (
                    "<p>Intro <a href=\"https://example.com\">example link</a></p>"
                    "<ol><li>First step</li><li>Second step</li></ol>"
                )
            },
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
    assert "<p>" not in rendered
    assert "<ol>" not in rendered
    assert "[example link](https://example.com)" in rendered
    assert "1. First step" in rendered
    assert "2. Second step" in rendered


def test_render_markdown_leaves_existing_markdown_content_unchanged() -> None:
    rendered = render_markdown(
        {
            "metadata": {"id": "1234", "title": "Example Page", "version": 2},
            "content": {"value": "## Runbook\n\n- Use the checklist."},
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
    assert "## Runbook" in rendered
    assert "- Use the checklist." in rendered


def test_render_markdown_unwraps_nested_page_envelope() -> None:
    rendered = render_markdown(
        {
            "message": "Page updated successfully",
            "page": {
                "metadata": {"id": "1234", "title": "Example Page", "version": 2},
                "content": {"value": "## Runbook\n\nUse the checklist."},
            },
        }
    )

    assert rendered.startswith("# 1234 - Example Page")
    assert "## Content" in rendered
