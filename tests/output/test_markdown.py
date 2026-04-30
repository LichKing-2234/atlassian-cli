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


def test_render_markdown_expands_remaining_detail_fields() -> None:
    payload = {
        "key": "DEMO-1",
        "summary": "Example issue summary",
        "status": {"name": "Open"},
        "priority": {"name": "High"},
        "project": {"key": "DEMO", "name": "Demo Project"},
        "labels": ["platform", "release"],
        "attachments": [
            {
                "id": "9001",
                "filename": "trace.txt",
                "mime_type": "text/plain",
            }
        ],
        "url": "https://example.invalid/rest/api/2/issue/DEMO-1",
        "description": "Investigate the release pipeline",
    }

    rendered = render_markdown(payload)

    assert rendered.startswith("# DEMO-1 - Example issue summary")
    assert "- Status: Open" in rendered
    assert "- Priority: High" in rendered
    assert "- Project: DEMO" in rendered
    assert "- URL: https://example.invalid/rest/api/2/issue/DEMO-1" in rendered
    assert "## Labels" in rendered
    assert "- platform" in rendered
    assert "- release" in rendered
    assert "## Attachments" in rendered
    assert "trace.txt" in rendered
    assert "- Mime Type: text/plain" in rendered
    assert "## Description" in rendered


def test_render_markdown_renders_nested_object_lists_as_detail_sections() -> None:
    payload = {
        "id": 42,
        "title": "Example pull request",
        "state": "OPEN",
        "reviewers": [
            {"display_name": "reviewer-one", "approved": True},
            {"display_name": "reviewer-two", "approved": False},
        ],
        "participants": [
            {
                "status": "APPROVED",
                "user": {"display_name": "Example Collaborator"},
            }
        ],
    }

    rendered = render_markdown(payload)

    assert rendered.startswith("# 42 - Example pull request")
    assert "- State: OPEN" in rendered
    assert "## Reviewers" in rendered
    assert "reviewer-one" in rendered
    assert "- Approved: True" in rendered
    assert "## Participants" in rendered
    assert "Example Collaborator" in rendered
