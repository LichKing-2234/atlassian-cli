from atlassian_cli.products.confluence.services.attachment import AttachmentService


class FakeAttachmentProvider:
    def list_attachments(self, page_id: str) -> dict:
        return {
            "results": [
                {
                    "id": "55",
                    "title": "deploy.log",
                    "_links": {"download": "/download/attachments/55/deploy.log"},
                }
            ]
        }

    def upload_attachment(self, page_id: str, file_path: str) -> dict:
        return {"id": "55", "title": "deploy.log"}

    def download_attachment(self, attachment_id: str, destination: str) -> dict:
        return {
            "attachment_id": attachment_id,
            "title": "deploy.log",
            "path": destination,
            "bytes_written": 21,
        }


def test_attachment_service_download_returns_provider_payload() -> None:
    service = AttachmentService(provider=FakeAttachmentProvider())

    result = service.download("55", "/tmp/deploy.log")

    assert result == {
        "attachment_id": "55",
        "title": "deploy.log",
        "path": "/tmp/deploy.log",
        "bytes_written": 21,
    }
