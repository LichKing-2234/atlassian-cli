from atlassian_cli.products.confluence.schemas import ConfluenceAttachment


class AttachmentService:
    def __init__(self, provider) -> None:
        self.provider = provider

    def list(self, page_id: str) -> "list[dict]":
        return [
            self._normalize_attachment(item) for item in self.provider.list_attachments(page_id)
        ]

    def list_raw(self, page_id: str) -> "list[dict]":
        return self.provider.list_attachments(page_id)

    def upload(self, page_id: str, file_path: str) -> dict:
        return self._normalize_attachment(self.provider.upload_attachment(page_id, file_path))

    def upload_raw(self, page_id: str, file_path: str) -> dict:
        return self.provider.upload_attachment(page_id, file_path)

    def download(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def download_raw(self, attachment_id: str, destination: str) -> dict:
        return self.provider.download_attachment(attachment_id, destination)

    def _normalize_attachment(self, raw: dict) -> dict:
        attachment = ConfluenceAttachment(
            id=str(raw.get("id", "")),
            title=raw.get("title") or raw.get("fileName") or "",
            media_type=(
                raw.get("mediaType")
                or ((raw.get("metadata") or {}).get("mediaType"))
                or ((raw.get("extensions") or {}).get("mediaType"))
            ),
        )
        return attachment.model_dump(exclude_none=True)
