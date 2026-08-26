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


def test_attachment_service_decodes_base64_upload_content() -> None:
    calls = {}

    class FakeProvider(FakeAttachmentProvider):
        def upload_attachment(self, page_id: str, file_path: str | None, **kwargs) -> dict:
            calls["args"] = (page_id, file_path, kwargs)
            return {"id": "55", "title": kwargs["filename"]}

    service = AttachmentService(provider=FakeProvider())

    result = service.upload(
        "1234",
        None,
        content_base64="ZXhhbXBsZSByZXNwb25zZQ==",
        filename="diagram.png",
        comment="example comment",
        minor_edit=True,
    )

    assert result == {"id": "55", "title": "diagram.png"}
    assert calls["args"] == (
        "1234",
        None,
        {
            "content": b"example response",
            "filename": "diagram.png",
            "comment": "example comment",
            "minor_edit": True,
        },
    )


def test_attachment_service_upload_many_normalizes_every_result() -> None:
    calls = {}

    class FakeProvider(FakeAttachmentProvider):
        def upload_attachments(self, content_id, file_paths, *, comment, minor_edit):
            calls["args"] = (content_id, file_paths, comment, minor_edit)
            return [
                {"id": "55", "title": "diagram.png"},
                {"id": "56", "title": "report.pdf"},
            ]

    result = AttachmentService(provider=FakeProvider()).upload_many(
        "1234",
        ["diagram.png", "report.pdf"],
        comment="example comment",
        minor_edit=True,
    )

    assert calls["args"] == (
        "1234",
        ["diagram.png", "report.pdf"],
        "example comment",
        True,
    )
    assert result == {
        "message": "Uploaded 2 attachment(s) successfully",
        "attachments": [
            {"id": "55", "title": "diagram.png"},
            {"id": "56", "title": "report.pdf"},
        ],
    }


def test_attachment_service_delete_returns_confirmation() -> None:
    calls = []

    class FakeProvider(FakeAttachmentProvider):
        def delete_attachment(self, attachment_id):
            calls.append(attachment_id)
            return {"attachment_id": attachment_id, "deleted": True}

    service = AttachmentService(provider=FakeProvider())

    assert service.delete("55") == {"attachment_id": "55", "deleted": True}
    assert service.delete_raw("56") == {"attachment_id": "56", "deleted": True}
    assert calls == ["55", "56"]
