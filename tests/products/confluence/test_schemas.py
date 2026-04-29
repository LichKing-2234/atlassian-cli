from atlassian_cli.products.confluence.schemas import (
    ConfluenceAttachment,
    ConfluencePage,
    ConfluenceSpace,
)


def test_confluence_page_from_api_response_builds_rich_resource() -> None:
    page = ConfluencePage.from_api_response(
        {
            "id": 1234,
            "title": "Example Page",
            "type": "page",
            "status": "current",
            "space": {"id": 7, "key": "PROJ", "name": "Demo Project"},
            "version": {"number": 3, "by": {"displayName": "Alice"}},
            "history": {"createdDate": "2026-04-20T10:00:00.000Z"},
        },
        base_url="https://confluence.example.com",
        is_cloud=False,
    )

    simplified = page.to_simplified_dict()

    assert simplified["space"]["key"] == "PROJ"
    assert simplified["version"] == 3
    assert "url" in simplified


def test_confluence_space_from_api_response_keeps_status_and_type() -> None:
    space = ConfluenceSpace.from_api_response(
        {"id": 9, "key": "PROJ", "name": "Demo Project", "type": "global", "status": "current"}
    )

    assert space.to_simplified_dict() == {
        "id": "9",
        "key": "PROJ",
        "name": "Demo Project",
        "type": "global",
        "status": "current",
    }


def test_confluence_attachment_from_api_response_reads_download_metadata() -> None:
    attachment = ConfluenceAttachment.from_api_response(
        {
            "id": 55,
            "title": "deploy.log",
            "_links": {"download": "/download/attachments/55/deploy.log"},
            "extensions": {"mediaType": "text/plain", "fileSize": 42},
            "version": {"number": 2, "by": {"displayName": "Alice"}},
        }
    )

    simplified = attachment.to_simplified_dict()

    assert simplified["download_url"] == "/download/attachments/55/deploy.log"
    assert simplified["file_size"] == 42
    assert simplified["author_display_name"] == "Alice"
