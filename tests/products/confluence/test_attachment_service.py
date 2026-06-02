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


def test_attachment_service_download_by_page_and_name() -> None:
    class FakeProvider(FakeAttachmentProvider):
        def download_attachment_from_content(
            self, page_id: str, name: str, destination: str
        ) -> dict:
            assert page_id == "1234"
            assert name == "deploy.log"
            assert destination == "/tmp/deploy.log"
            return {
                "page_id": page_id,
                "attachment_id": "55",
                "title": name,
                "path": destination,
                "bytes_written": 21,
            }

    service = AttachmentService(provider=FakeProvider())

    result = service.download_from_content("1234", name="deploy.log", destination="/tmp/deploy.log")

    assert result["attachment_id"] == "55"
    assert result["bytes_written"] == 21
