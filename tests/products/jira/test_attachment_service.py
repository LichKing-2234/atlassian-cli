import pytest

from atlassian_cli.products.jira.services.attachment import AttachmentService


class FakeAttachmentProvider:
    def list_issue_attachments(self, issue_key: str) -> list[dict]:
        assert issue_key == "DEMO-1"
        return [
            {
                "id": "10001",
                "filename": "report.pdf",
                "size": 42,
                "mimeType": "application/pdf",
                "content": "attachment://DEMO-1/report.pdf",
            }
        ]

    def upload_issue_attachment(self, issue_key: str, file_path: str) -> dict:
        assert issue_key == "DEMO-1"
        assert file_path == "/tmp/report.pdf"
        return {"id": "10001", "filename": "report.pdf", "size": 42}

    def download_issue_attachment(
        self, attachment: dict, destination: str, *, issue_key: str
    ) -> dict:
        assert attachment["id"] == "10001"
        assert destination == "/tmp/report.pdf"
        assert issue_key == "DEMO-1"
        return {
            "issue_key": "DEMO-1",
            "attachment_id": "10001",
            "filename": "report.pdf",
            "path": "/tmp/report.pdf",
            "bytes_written": 15,
        }


def test_attachment_service_list_normalizes_results() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.list("DEMO-1")

    assert result == {
        "results": [
            {
                "id": "10001",
                "filename": "report.pdf",
                "size": 42,
                "mime_type": "application/pdf",
                "download_url": "attachment://DEMO-1/report.pdf",
            }
        ]
    }


def test_attachment_service_upload_normalizes_result() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.upload("DEMO-1", "/tmp/report.pdf")

    assert result == {"id": "10001", "filename": "report.pdf", "size": 42}


def test_attachment_service_download_by_name() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.download("DEMO-1", name="report.pdf", destination="/tmp/report.pdf")

    assert result["attachment_id"] == "10001"
    assert result["bytes_written"] == 15


def test_attachment_service_download_missing_name_raises_clear_error() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    with pytest.raises(ValueError, match="No attachment named missing.pdf"):
        service.download("DEMO-1", name="missing.pdf", destination="/tmp/missing.pdf")
